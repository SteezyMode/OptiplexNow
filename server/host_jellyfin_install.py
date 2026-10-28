#!/usr/bin/env python3
"""Narrow clean-host Jellyfin installer pilot. NEVER auto-enabled by the .deb.

--check is read-only. --install requires local OS authorization (pkexec),
explicit image SHA256 and media folder, and a second privileged recheck.
Never deploy on an existing Jellyfin server or the developer reference host.
All new state is isolated to a dedicated owner-approved Compose project.
"""
from __future__ import annotations

import argparse
import fcntl
import ipaddress
import json
import os
from pathlib import Path
import platform
import pwd
import shutil
import re
import socket
import stat
import subprocess
import sys

import host_services

BASE = Path("/var/lib/optiplex-now")
WORKSPACE = BASE / "jellyfin-host-pilot"
LOCK = Path("/run/optiplex-now-jellyfin-install.lock")
PROJECT = "optiplex-now-jellyfin-pilot"
IMAGE_BASE = "jellyfin/jellyfin@sha256:"
DIGEST = re.compile(r"[a-f0-9]{64}\Z")
PORT = 8096
MAX_OUTPUT = 32768
DOCKER_VERSION = re.compile(r"(\d+)\.(\d+)\.(\d+)(?:[-+][A-Za-z0-9_.-]+)?\Z")
STOP_PREFIXES = (Path("/etc"), Path("/root"), Path("/proc"), Path("/sys"),
                 Path("/dev"), Path("/run"), Path("/usr"), Path("/var"),
                 Path("/tmp"), Path("/boot"))


class JellyfinInstallError(RuntimeError):
    pass


def _invoke(args, *, timeout=12):
    try:
        p = subprocess.run(args, stdin=subprocess.DEVNULL, capture_output=True,
                           timeout=timeout, check=False, text=True,
                           env={"PATH":"/usr/bin:/bin",
                                "HOME":"/nonexistent/now-jellyfin-pilot",
                                "DOCKER_CONFIG":"/nonexistent/now-docker-pilot"})
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise JellyfinInstallError("Local dependency unavailable or timed out") from exc
    if p.returncode or len(p.stdout) > MAX_OUTPUT:
        raise JellyfinInstallError("Local dependency failed; inspect its state")
    return p.stdout.strip()


def _supported_os():
    """Keep the pilot host matrix aligned with the existing Wolf installer."""
    if platform.machine() != "x86_64":
        return False
    try:
        details = Path("/etc/os-release").read_text(encoding="utf-8")[:8192]
    except OSError:
        return False
    fields = {}
    for line in details.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            if k in ("ID", "VERSION_ID"):
                fields[k] = v.strip('"')
    return fields.get("ID") in ("ubuntu", "pop") and fields.get("VERSION_ID") == "24.04"


def _enough_disk():
    try:
        available = shutil.disk_usage(BASE if BASE.exists() else BASE.parent).free
    except OSError:
        return False
    return available >= 5 * 1024**3



def _docker_network_gate():
    """Require an engine without Docker's documented pre-28 localhost leak.

    This is a necessary condition, not proof of end-to-end Tailnet isolation:
    Docker's forwarding/NAT and the local network still require live checks.
    """
    try:
        server_version = _invoke(
            ["/usr/bin/docker", "version", "--format", "{{.Server.Version}}"])
    except JellyfinInstallError:
        return False
    version = DOCKER_VERSION.fullmatch(server_version)
    return bool(version and tuple(map(int, version.groups()[:3])) >= (28, 0, 0))


def _expected_ports(tail_ip):
    return {("127.0.0.1", str(PORT)), (tail_ip, str(PORT))}


def _verified_container(item, *, cid, image, tail_ip, media_path, owner_uid,
                        owner_gid, workspace=None):
    """Post-start check of the *actual* Docker published ports and media mount.

    A running container is not equivalent to a private or functioning Jellyfin
    server. No raw inspect metadata is returned to the user.
    """
    if not isinstance(item, dict) or item.get("Id") != cid:
        return False
    config, host_cfg, net, state = (item.get(k) for k in
        ("Config", "HostConfig", "NetworkSettings", "State"))
    if not all(isinstance(x, dict) for x in (config, host_cfg, net, state)):
        return False
    labels = config.get("Labels")
    if not isinstance(labels, dict) or (
            state.get("Running") is not True or
            config.get("Image") != image or
            config.get("User") != f"{owner_uid}:{owner_gid}" or
            labels.get("com.docker.compose.project") != PROJECT or
            labels.get("io.optiplex-now.managed") != "jellyfin-host-pilot" or
            host_cfg.get("NetworkMode") in ("host", "none")):
        return False
    mappings = net.get("Ports")
    if not isinstance(mappings, dict) or "8096/tcp" not in mappings:
        return False
    # Unpublished ports EXPOSEd by the upstream image may appear as null,
    # but any additional published binding is an unexpected exposure.
    if any(key != "8096/tcp" and published is not None
           for key, published in mappings.items()):
        return False
    addresses = mappings["8096/tcp"]
    if not isinstance(addresses, list) or len(addresses) != 2:
        return False
    observed = set()
    for address in addresses:
        if (not isinstance(address, dict) or
                set(address) != {"HostIp", "HostPort"} or
                not isinstance(address["HostIp"], str) or
                not isinstance(address["HostPort"], str)):
            return False
        observed.add((address["HostIp"], address["HostPort"]))
    if len(observed) != 2 or observed != _expected_ports(tail_ip):
        return False
    mounts = item.get("Mounts")
    if not isinstance(mounts, list) or len(mounts) != 3:
        return False
    if workspace is None:
        workspace = WORKSPACE
    expected = {
        "/config": (str(workspace / "config"), True),
        "/cache": (str(workspace / "cache"), True),
        "/media/library": (media_path, False),
    }
    seen = set()
    for mount in mounts:
        if (not isinstance(mount, dict) or
                mount.get("Type") != "bind" or
                mount.get("Destination") not in expected or
                not isinstance(mount.get("RW"), bool)):
            return False
        dest = mount["Destination"]
        if dest in seen or (mount.get("Source"), mount["RW"]) != expected[dest]:
            return False
        seen.add(dest)
    return seen == set(expected)


def _trusted_directory(path):
    try:
        st = path.lstat()
    except FileNotFoundError:
        return False
    return (stat.S_ISDIR(st.st_mode) and st.st_uid == 0 and
            (stat.S_IMODE(st.st_mode) & 0o022) == 0)


def media_root_for_owner(path_text, uid, *, is_allowed=True):
    """Approved existing owner directory. No symlinks anywhere in its path."""
    if type(uid) is not int or uid <= 0 or not isinstance(path_text, str) or (
            not path_text.startswith("/") or len(path_text) > 1024 or
            "\x00" in path_text or "\n" in path_text):
        raise JellyfinInstallError("Invalid media library directory")
    path = Path(path_text)
    if ".." in path.parts or path == Path("/") or any(
            path == prefix or prefix in path.parents for prefix in STOP_PREFIXES):
        raise JellyfinInstallError("Media library location is not eligible")
    current = Path("/")
    for part in path.parts[1:]:
        current = current / part
        try:
            st = current.lstat()
        except OSError as exc:
            raise JellyfinInstallError("Media library directory not accessible") from exc
        if not stat.S_ISDIR(st.st_mode):
            raise JellyfinInstallError("Media path must be an existing directory without symlinks")
    st = path.lstat()
    if st.st_uid != uid or not (st.st_mode & stat.S_IRUSR and st.st_mode & stat.S_IXUSR):
        raise JellyfinInstallError("Media directory must be readable and owned by the host owner")
    if WORKSPACE == path or WORKSPACE in path.parents or path in WORKSPACE.parents:
        raise JellyfinInstallError("Managed state cannot be used as a media library")
    return str(path)


def _tailnet_ipv4():
    raw = _invoke(["/usr/bin/tailscale", "ip", "-4"])
    ips = raw.split()
    if len(ips) != 1:
        raise JellyfinInstallError("A unique Tailscale IPv4 is required")
    try:
        ip = ipaddress.IPv4Address(ips[0])
    except ipaddress.AddressValueError as exc:
        raise JellyfinInstallError("Invalid Tailscale IPv4") from exc
    if ip not in ipaddress.IPv4Network("100.64.0.0/10"):
        raise JellyfinInstallError("Host Tailscale address is not in the approved range")
    return str(ip)


def _ports_free(tail_ip):
    # Read-only reachability preflight; final Docker bind remains authoritative.
    for ip in ("127.0.0.1", tail_ip):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind((ip, PORT))
            except OSError:
                return False
    return True


def _project_is_clear():
    """Never attach to an existing Compose project of the same name."""
    try:
        ids = _invoke(["/usr/bin/docker", "ps", "-aq",
                       "--filter", f"label=com.docker.compose.project={PROJECT}"])
    except JellyfinInstallError:
        return False
    return not bool(ids)


def assess(media_path, digest, uid, *, privileged=False,
           docker_report=None, tail_ip=None, compose_ready=None,
           ports_ready=None, system_ok=None, disk_ok=None,
           project_clear=None, docker_network_ok=None):
    """Pure-ish preflight; inject runtime evidence for isolated CI tests."""
    blockers = []
    if system_ok is None:
        system_ok = _supported_os()
    if not system_ok:
        blockers.append("Supported host requires Ubuntu/Pop!_OS 24.04 amd64")
    if disk_ok is None:
        disk_ok = _enough_disk()
    if not disk_ok:
        blockers.append("At least 5 GiB free on the managed state disk is required")
    if not isinstance(digest, str) or not DIGEST.fullmatch(digest):
        blockers.append("A verified immutable Jellyfin SHA256 image digest is required")
    try:
        media_root_for_owner(media_path, uid)
    except JellyfinInstallError as exc:
        blockers.append(str(exc))
    if BASE.is_symlink() or (BASE.exists() and not _trusted_directory(BASE)):
        blockers.append("NOW host state parent is not trusted")
    if WORKSPACE.exists() or WORKSPACE.is_symlink():
        blockers.append("Jellyfin pilot workspace already exists; manual review required")
    if docker_report is None:
        docker_report = host_services.collect()
    if docker_report.get("docker_access") != "available":
        blockers.append("Docker inventory unavailable; no install allowed")
    elif docker_report.get("services", {}).get("jellyfin", {}).get(
            "status") != "not_detected_in_docker":
        blockers.append("Existing Jellyfin Docker candidate; adopt instead")
    if compose_ready is None:
        try:
            _invoke(["/usr/bin/docker", "compose", "version"])
            compose_ready = True
        except JellyfinInstallError:
            compose_ready = False
    if not compose_ready:
        blockers.append("Docker Compose unavailable")
    if docker_network_ok is None:
        docker_network_ok = _docker_network_gate()
    if not docker_network_ok:
        blockers.append("Docker Engine 28.0.0+ required for safe localhost publishing")
    if project_clear is None:
        project_clear = _project_is_clear()
    if not project_clear:
        blockers.append("NOW Jellyfin Compose project already exists or could not be inspected")
    if tail_ip is None:
        try:
            tail_ip = _tailnet_ipv4()
        except JellyfinInstallError:
            blockers.append("Approved Tailscale IPv4 unavailable")
    else:
        try:
            if ipaddress.IPv4Address(tail_ip) not in ipaddress.IPv4Network("100.64.0.0/10"):
                raise ValueError("Not Tailscale IPv4")
        except ValueError:
            blockers.append("Invalid Tailscale IPv4")
    if tail_ip and "Invalid Tailscale IPv4" not in blockers:
        if ports_ready is None:
            ports_ready = _ports_free(tail_ip)
        if not ports_ready:
            blockers.append("Local loopback or Tailscale Jellyfin port is occupied")
    if not privileged:
        blockers.append("Installer requires a fresh OS-authorized administrator recheck")
    return {
        "tool":"now-jellyfin-clean-host", "schema_version":1,
        "status":"candidate_after_admin_check" if not blockers else "blocked",
        "read_only":True, "changes_performed":False, "blockers":blockers,
        "scope":"new_jellyfin_only",
        "note":"No media files, Docker services or ports changed by this check.",
    }


def render_compose(*, image_digest, media_root, owner_uid, owner_gid, tail_ip,
                   workspace=WORKSPACE):
    if not DIGEST.fullmatch(image_digest):
        raise JellyfinInstallError("Unverified image digest")
    media_root_for_owner(media_root, owner_uid)
    ip = ipaddress.IPv4Address(tail_ip)
    if ip not in ipaddress.IPv4Network("100.64.0.0/10"):
        raise JellyfinInstallError("Untrusted published bind address")
    service = {
        "image":IMAGE_BASE + image_digest,
        "user":f"{owner_uid}:{owner_gid}",
        "restart":"unless-stopped",
        "labels":{"io.optiplex-now.managed":"jellyfin-host-pilot"},
        "security_opt":["no-new-privileges:true"],
        "cap_drop":["ALL"],
        "ports":[
            {"target":8096,"published":"8096","host_ip":"127.0.0.1","protocol":"tcp"},
            {"target":8096,"published":"8096","host_ip":str(ip),"protocol":"tcp"},
        ],
        "volumes":[
            {"type":"bind","source":str(workspace / "config"),"target":"/config"},
            {"type":"bind","source":str(workspace / "cache"),"target":"/cache"},
            {"type":"bind","source":media_root,"target":"/media/library","read_only":True},
        ],
    }
    return json.dumps({"services":{"jellyfin":service}}, indent=2) + "\n"


def _new_file(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        raw = data.encode("utf-8")
        offset = 0
        while offset < len(raw):
            n = os.write(fd, raw[offset:])
            if n <= 0:
                raise JellyfinInstallError("Incomplete Jellyfin setup journal")
            offset += n
        os.fsync(fd)
    finally:
        os.close(fd)


def _journal(status, image):
    # Root-only state; never advertise actual playable media until the user
    # finishes Jellyfin's independent login/setup in its own browser.
    data = json.dumps({"schema_version":1,"status":status,"image":image,
                       "playback_verified":False}) + "\n"
    _new_file(WORKSPACE / f"phase-{status}.json", data)


def install(media_path, digest, owner_uid, confirmation):
    if os.geteuid() != 0 or confirmation != "INSTALL-JELLYFIN":
        raise JellyfinInstallError("Local OS-approved confirmation required")
    try:
        authenticated_uid = int(os.environ["PKEXEC_UID"])
        user = pwd.getpwuid(authenticated_uid)
    except (KeyError, ValueError) as exc:
        raise JellyfinInstallError("Authenticated invoking host owner required") from exc
    if authenticated_uid <= 0 or owner_uid != authenticated_uid:
        raise JellyfinInstallError("Host owner identity mismatch")
    if not DIGEST.fullmatch(digest):
        raise JellyfinInstallError("Pinned Jellyfin image digest required")
    fd = os.open(LOCK, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        report = assess(media_path, digest, owner_uid, privileged=True)
        if report["blockers"]:
            raise JellyfinInstallError("Clean-host preflight refused; do not retry without review")
        if not BASE.exists():
            BASE.mkdir(mode=0o700)
        if not _trusted_directory(BASE):
            raise JellyfinInstallError("Untrusted managed host parent")
        WORKSPACE.mkdir(mode=0o700)
        image = IMAGE_BASE + digest
        _journal("preparing", image)
        for folder in ("config", "cache"):
            p = WORKSPACE / folder
            p.mkdir(mode=0o700)
            os.chown(p, user.pw_uid, user.pw_gid)
        tail_ip = _tailnet_ipv4()
        if not _ports_free(tail_ip):
            raise JellyfinInstallError("Port changed after eligibility check; inspect setup")
        data = render_compose(image_digest=digest, media_root=media_path,
                              owner_uid=user.pw_uid, owner_gid=user.pw_gid,
                              tail_ip=tail_ip)
        _new_file(WORKSPACE / "compose.json", data)
        _journal("pulling", image)
        _invoke(["/usr/bin/docker", "pull", image], timeout=600)
        _journal("starting", image)
        base = ["/usr/bin/docker", "compose", "-p", PROJECT,
                "-f", str(WORKSPACE / "compose.json")]
        _invoke(base + ["up", "-d", "--no-build", "--no-recreate"], timeout=180)
        cid = _invoke(base + ["ps", "-q", "jellyfin"])
        if not re.fullmatch("[0-9a-f]{64}", cid):
            raise JellyfinInstallError("Jellyfin container not uniquely identified")
        raw = _invoke(["/usr/bin/docker", "inspect", "--type", "container", cid])
        details = json.loads(raw)
        if not isinstance(details, list) or len(details) != 1:
            raise JellyfinInstallError("Unexpected Jellyfin container metadata")
        item = details[0]
        if not _verified_container(
                item, cid=cid, image=image, tail_ip=tail_ip,
                media_path=media_path, owner_uid=user.pw_uid,
                owner_gid=user.pw_gid):
            raise JellyfinInstallError(
                "Jellyfin runtime ports, media mounts or identity not verified")
        _journal("running_media_unverified", image)
        return {"tool":"now-jellyfin-clean-host", "schema_version":1,
                "status":"running_media_unverified", "changes_performed":True,
                "note":"Open Jellyfin for first-run account setup. No playback accepted yet."}
    finally:
        os.close(fd)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    actions = p.add_mutually_exclusive_group(required=True)
    actions.add_argument("--check", action="store_true")
    actions.add_argument("--install", action="store_true")
    p.add_argument("--media-path", required=True)
    p.add_argument("--image-digest", required=True)
    p.add_argument("--owner-uid", required=True, type=int)
    p.add_argument("--confirm", default="")
    a = p.parse_args(argv)
    try:
        if a.check:
            # Real eligibility is always privileged and repeated at install.
            report = assess(a.media_path, a.image_digest, a.owner_uid,
                            privileged=os.geteuid() == 0 and bool(os.environ.get("PKEXEC_UID")))
        else:
            report = install(a.media_path, a.image_digest, a.owner_uid, a.confirm)
    except (OSError, ValueError, JellyfinInstallError, subprocess.TimeoutExpired):
        print(json.dumps({"tool":"now-jellyfin-clean-host","schema_version":1,
                          "status":"refused_or_interrupted",
                          "changes_performed":"unknown" if a.install else False,
                          "note":"Review host setup and existing state before retry."}))
        return 1
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] != "blocked" else 2


if __name__ == "__main__":
    raise SystemExit(main())
