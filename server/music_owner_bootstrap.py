"""Host-only, no-signup DroppedNeedle owner initialization for a NEW Bruiser host.

Only invoke locally when the chosen DroppedNeedle instance has no users.
No passwords/keys are printed, sent to clients, GitHub or program arguments.
Existing DroppedNeedle owners are NEVER overwritten or reset. For established
hosts, explicit owner-account recovery/linking remains necessary.

This is a component of the eventual GUI host installer, not a deployed setup
action and not a remote SSH command.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
from pathlib import Path
import secrets
import stat
import sys
from urllib.parse import urlsplit

from owner_access import OwnerStore, PolicyError
from music_device_provision import DroppedNeedleAPI, ProvisionError

MAX_FILE = 4096
DEFAULT_ACCOUNT = Path.home() / ".config/optiplex-now/owner-music-host.json"


def _validate_local_target(base_url: str) -> str:
    from music_subsonic import endpoint_for, MusicTransportError
    try:
        endpoint_for(base_url, "ping")
        parts = urlsplit(base_url)
    except (MusicTransportError, ValueError) as exc:
        raise ProvisionError("Music owner setup requires a local server address.") from exc
    # Initial admin creation must not cross the network or a reverse proxy.
    if parts.hostname not in ("127.0.0.1", "::1"):
        raise ProvisionError("Initial Music owner setup must run on the server loopback.")
    return base_url


def _private_config_dir(account_path: Path) -> None:
    folder=account_path.parent
    if folder.is_symlink():
        raise PolicyError("Unsafe Music account directory")
    try:
        folder.mkdir(mode=0o700,parents=True,exist_ok=True)
    except OSError as exc:
        raise PolicyError("Cannot create private Music account directory") from exc
    info=folder.stat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid!=os.geteuid()
            or stat.S_IMODE(info.st_mode)!=0o700):
        raise PolicyError("Music owner account directory must be private (0700)")


def _write_once(path: Path, record: dict) -> None:
    raw=(json.dumps(record,sort_keys=True,separators=(",",":"))+"\n").encode()
    if len(raw)>MAX_FILE:
        raise ProvisionError("Music owner account data is too large.")
    flags=os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,"O_NOFOLLOW",0)
    fd=os.open(path,flags,0o600)
    try:
        with os.fdopen(fd,"wb",closefd=False) as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(fd)
    finally:
        os.close(fd)
    # Commit directory entry so an unexpected shutdown cannot erase the only
    # copy of the generated secret after the upstream account is created.
    dfd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY|getattr(os,"O_NOFOLLOW",0))
    try:
        os.fsync(dfd)
    finally:
        os.close(dfd)


def bootstrap_owner_account(*, state_dir: str, base_url: str,
                            account_path: Path = DEFAULT_ACCOUNT,
                            api_factory=DroppedNeedleAPI) -> str:
    """Create only the first DN admin for the existing NOW owner principal.

    Returns a non-secret status. Credentials are stored on the host in a
    private 0600 file BEFORE calling DN /auth/setup to prevent crash-loss.
    A prepared file remains after a failed upstream setup for explicit
    owner-reviewed recovery; never delete a possibly valid credential.
    """
    _validate_local_target(base_url)
    account_path=Path(account_path)
    _private_config_dir(account_path)
    store=OwnerStore(state_dir)
    with store.locked() as fd:
        policy=store.read(fd)
        if not policy or not isinstance(policy.get("principals"),list):
            raise PolicyError("Approve the local NOW server owner first.")
        principal=policy["principals"][0]["id"]
        api=api_factory(base_url)
        lock_path=account_path.parent / ".owner-music-bootstrap.lock"
        lockfd=os.open(lock_path,os.O_CREAT|os.O_RDWR|
                       getattr(os,"O_NOFOLLOW",0),0o600)
        try:
            meta=os.fstat(lockfd)
            if (not stat.S_ISREG(meta.st_mode) or meta.st_uid!=os.geteuid()
                    or stat.S_IMODE(meta.st_mode)!=0o600):
                raise PolicyError("Unsafe Music bootstrap lock")
            fcntl.flock(lockfd,fcntl.LOCK_EX)
            if account_path.exists() or account_path.is_symlink():
                from owner_music_ssh import read_owner_music_account
                existing=read_owner_music_account(account_path)
                if (existing["owner_principal_id"]!=principal or
                        existing["base_url"]!=base_url):
                    raise PolicyError("Music owner account belongs to another host.")
                # A successfully initialized account is idempotent. A
                # prepared-but-failed account must NOT be blindly replaced.
                api.login(existing["username"],existing["password"])
                return "already-linked"
            status=api.call("GET","/auth/setup/status")
            if status.get("required") is not True:
                raise ProvisionError(
                    "This Music server already has users. Use existing-owner recovery.")
            record={
                "version":1,
                "base_url":base_url,
                "owner_principal_id":principal,
                "username":"bruiser_owner",
                "password":secrets.token_urlsafe(48),
            }
            _write_once(account_path,record)
            # The single user isn't exposed to clients and is created only
            # through DroppedNeedle's own guarded first-admin endpoint.
            result=api.call("POST","/auth/setup",data={
                "display_name":"Bruiser Owner",
                "username":record["username"],
                "password":record["password"],
            })
            user=result.get("user")
            if not isinstance(user,dict) or user.get("role")!="admin":
                raise ProvisionError(
                    "Music setup returned an unexpected owner; investigate before retrying.")
            return "created"
        finally:
            fcntl.flock(lockfd,fcntl.LOCK_UN)
            os.close(lockfd)


def main(argv=None) -> int:
    parser=argparse.ArgumentParser(description="Host-only first Music owner initialization")
    parser.add_argument("--state-dir",required=True,
                        help="Path to the configured NOW owner state directory")
    parser.add_argument("--local-music-url",required=True,
                        help="Existing DroppedNeedle loopback URL (no passwords)")
    args=parser.parse_args(argv)
    try:
        status=bootstrap_owner_account(state_dir=args.state_dir,
                                       base_url=args.local_music_url)
    except (PolicyError,ProvisionError,OSError,ValueError):
        print("Music owner setup needs local administrator attention.")
        return 1
    print("Music owner connected." if status=="already-linked"
          else "Initial Music account securely configured.")
    return 0


if __name__=="__main__":
    sys.exit(main())
