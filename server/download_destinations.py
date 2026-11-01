"""Owner-only download library destinations and explicit magnet enqueue.

Host-local adapter; the restricted owner broker authorizes each request.
Writable storage mounts are discovered from the verified qBittorrent container.
Never expose host root or service configuration mounts as download targets.
Existing host directories and mounts are never modified by browsing.
"""
import hashlib
import os
from pathlib import Path
import re
import subprocess
from urllib.parse import urlencode

from download_inventory import _containers, InventoryError
from download_queue import locate_verified_downloader
from download_search import checked_magnet

ROOT_ID = re.compile(r"[a-z][a-z0-9_-]{0,31}\Z")
MAX_RELATIVE = 512
MAX_DEPTH = 12
MAX_DIRS = 100
MAX_NAME = 160

class DestinationError(InventoryError):
    pass

def _mounts(*, runner=subprocess.run):
    gateway, port = locate_verified_downloader(runner=runner)
    records = _containers(runner=runner)
    candidates = [item for item in records
        if str(item.get("Config",{}).get("Image","")).lower()
        .split("/")[-1].split(":")[0] == "qbittorrent" and
        item.get("HostConfig",{}).get("NetworkMode","")
            in ("container:"+gateway,
                "container:"+next((g.get("Name","").lstrip("/")
                     for g in records if g.get("Id")==gateway),""))]
    if len(candidates)!=1:
        raise DestinationError("No unique bound downloader")
    qbit=candidates[0]
    roots={}
    excluded=("/config", "/etc", "/dev", "/proc", "/sys", "/run",
              "/root", "/usr", "/var", "/boot", "/opt")
    forbidden_sources=("/etc", "/root", "/usr", "/var", "/dev",
                       "/sys", "/proc", "/run", "/boot", "/opt")
    for entry in qbit.get("Mounts",[]):
        if (not isinstance(entry,dict) or entry.get("Type")!="bind"
                or entry.get("RW") is not True):
            continue
        target,source=entry.get("Destination"),entry.get("Source")
        if not isinstance(target,str) or not isinstance(source,str):
            continue
        if (not target.startswith("/") or target=="/"
                or os.path.normpath(target)!=target
                or any(target==p or target.startswith(p+"/") for p in excluded)):
            continue
        if (not os.path.isabs(source) or source=="/"
                or not os.path.isdir(source)):
            continue
        resolved=os.path.realpath(source)
        if (resolved!=source or os.path.islink(source)
                or any(resolved==p or resolved.startswith(p+"/")
                       for p in forbidden_sources)
                or resolved=="/home"):
            continue
        match=re.fullmatch(r"/library/([a-z][a-z0-9_-]{0,31})",target)
        if match:
            slug=match.group(1)
            label=slug.replace("_"," ").title()
        else:
            # Stable, opaque mount ID: no untrusted host path in requests.
            # Preserve existing /library/<slug> IDs and saved bookmarks.
            slug="mount_"+hashlib.sha256(target.encode("utf-8")).hexdigest()[:16]
            label=os.path.basename(resolved.rstrip("/")) or target.strip("/")
            label=label[:MAX_NAME]
        if slug in roots:
            raise DestinationError("Ambiguous downloader mount")
        roots[slug]={"source":source,"target":target,"label":label}
    if not roots or len(roots)>24:
        raise DestinationError("No usable writable downloader storage mounts")
    return qbit["Id"],gateway,port,roots

def _relative(value):
    if not isinstance(value,str) or len(value)>MAX_RELATIVE:
        raise DestinationError("Invalid media folder")
    if not value:
        return []
    parts=value.split("/")
    if (len(parts)>MAX_DEPTH or any(
            p in ("",".","..") or len(p)>MAX_NAME or
            any(ord(c)<32 or ord(c)==127 for c in p) for p in parts)):
        raise DestinationError("Unsafe media subfolder")
    return parts

def _open_folder(source,parts):
    flags=os.O_RDONLY|os.O_DIRECTORY|getattr(os,"O_NOFOLLOW",0)
    fd=os.open(source,flags)
    try:
        for component in parts:
            child=os.open(component,flags,dir_fd=fd)
            os.close(fd)
            fd=child
        return fd
    except (OSError,ValueError):
        os.close(fd)
        raise

def roots(*,runner=subprocess.run):
    _,_,_,mounts=_mounts(runner=runner)
    return {"roots":[{"id":name,"label":entry["label"]}
                     for name,entry in sorted(mounts.items(),
                                            key=lambda item:item[1]["label"].casefold())]}

def browse(root,relative="",*,runner=subprocess.run):
    if not isinstance(root,str) or not ROOT_ID.fullmatch(root):
        raise DestinationError("Unknown library root")
    _,_,_,mounts=_mounts(runner=runner)
    if root not in mounts:
        raise DestinationError("Library root not configured")
    components=_relative(relative)
    try:
        fd=_open_folder(mounts[root]["source"],components)
        try:
            folders=[]
            with os.scandir(fd) as entries:
                for item in entries:
                    if item.is_dir(follow_symlinks=False):
                        if (len(item.name)<=MAX_NAME and
                            not any(ord(c)<32 or ord(c)==127 for c in item.name)):
                            folders.append(item.name)
                            if len(folders)>MAX_DIRS:
                                raise DestinationError("Too many subfolders")
        finally:
            os.close(fd)
    except OSError as exc:
        raise DestinationError("Folder missing or inaccessible") from exc
    return {"root":root,"relative":relative,
            "folders":sorted(folders,key=str.casefold)}

def checked_folder_name(value):
    """A single new child in a verified existing library directory."""
    if (not isinstance(value, str) or not 1 <= len(value) <= MAX_NAME or
            value in (".", "..") or "/" in value or "\\" in value or
            any(ord(c) < 32 or ord(c) == 127 for c in value)):
        raise DestinationError("Invalid new folder name")
    return value


def create_folder(root, relative, name, *, runner=subprocess.run):
    """Create one directory inside a verified qBittorrent writable bind mount.

    Never accept host paths, create a new Docker mount, follow symlinks,
    or run a shell with caller-controlled input. This operation is only
    reachable through the independently authenticated restricted owner gate.
    """
    if not isinstance(root, str) or not ROOT_ID.fullmatch(root):
        raise DestinationError("Invalid library root")
    child = checked_folder_name(name)
    parts = _relative(relative)
    qbit, _gateway, _port, mounts = _mounts(runner=runner)
    if root not in mounts:
        raise DestinationError("Library root not configured")
    parent = mounts[root]["target"]
    if parts:
        parent += "/" + "/".join(parts)
    fd = None
    try:
        fd = _open_folder(mounts[root]["source"], parts)
        # The actual downloader user must have write access, not just the
        # host operator executing the restricted command.
        check = ["docker", "exec", "-u", "abc", qbit,
                 "sh", "-c", 'test -w "$1"', "now", parent]
        permission = runner(check, capture_output=True, timeout=6, check=False)
        if permission.returncode != 0:
            raise DestinationError("Downloader cannot write parent folder")
        try:
            os.mkdir(child, mode=0o775, dir_fd=fd)
        except FileExistsError as exc:
            raise DestinationError("Folder already exists") from exc
        # Verify newly created path is also writable by qBittorrent; avoid
        # advertising a location it cannot actually download into.
        new_path = parent + "/" + child
        permission = runner(["docker", "exec", "-u", "abc", qbit,
                             "sh", "-c", 'test -w "$1"', "now", new_path],
                            capture_output=True, timeout=6, check=False)
        if permission.returncode != 0:
            # Only roll back the empty directory created by this request.
            try:
                os.rmdir(child, dir_fd=fd)
            except OSError:
                pass
            raise DestinationError("Downloader cannot write new folder")
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise DestinationError("Unable to create approved folder") from exc
    finally:
        if fd is not None:
            os.close(fd)
    return {"status": "created"}


def add_magnet(root,relative,magnet,*,runner=subprocess.run):
    if not isinstance(root,str) or not ROOT_ID.fullmatch(root):
        raise DestinationError("Unknown library root")
    checked=checked_magnet(magnet)
    if checked is None:
        raise DestinationError("Only verified magnets may be added")
    components=_relative(relative)
    qbit,gateway,port,mounts=_mounts(runner=runner)
    if root not in mounts:
        raise DestinationError("Library root not configured")
    savepath=mounts[root]["target"]
    if components:
        savepath+="/"+"/".join(components)
    try:
        fd=_open_folder(mounts[root]["source"],components)
        os.close(fd)
    except OSError as exc:
        raise DestinationError("Destination must already exist") from exc
    # The downloader itself—not merely the remote SSH account—must be able
    # to write the target. No shell interpolation of the path.
    check=["docker","exec","-u","abc",qbit,
           "sh","-c",'test -w "$1"',"now",savepath]
    try:
        writable=runner(check,capture_output=True,timeout=6,check=False)
    except (OSError,subprocess.TimeoutExpired) as exc:
        raise DestinationError("Destination write check failed") from exc
    if writable.returncode:
        raise DestinationError("Downloader cannot write selected folder")
    # Explicit savepath; disable automatic category management to prevent
    # qBittorrent from silently overriding the selected genre directory.
    form=urlencode({"urls":checked,"savepath":savepath,"autoTMM":"false"})
    url=f"http://127.0.0.1:{port}/api/v2/torrents/add"
    # Same-origin Referer satisfies qBittorrent's local WebUI CSRF check;
    # the restricted owner broker has already authorized this exact Add.
    command=["docker","exec",gateway,"wget","-q","-T","5","-O","-",
             "--header",f"Referer: http://127.0.0.1:{port}/",
             "--post-data="+form,url]
    try:
        result=runner(command,capture_output=True,timeout=8,check=False)
    except (OSError,subprocess.TimeoutExpired) as exc:
        raise DestinationError("Downloader add unavailable") from exc
    if result.returncode or result.stdout.strip()!=b"Ok.":
        raise DestinationError("Downloader did not accept the torrent")
    return {"status":"submitted"}
