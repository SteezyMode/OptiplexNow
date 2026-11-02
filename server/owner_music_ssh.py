"""Host-only NOW Music issue action, behind the existing restricted owner SSH key.

Never call this from a general web endpoint. The caller must have verified
the SSH key's pinned Wolf client ID independently of every request field.
The owner must link the specific local DN account in a private 0600 host
file and explicitly grant Music to the device. No auto-grant on pairing.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import stat

from owner_access import OwnerStore, PolicyError, resolve_music, revoke_music
from music_device_ledger import (
    get_device_locked, record_issued_locked, remove_device_locked
)
from music_device_provision import (
    issue_approved_music_access, DroppedNeedleAPI, ProvisionError
)

ACCOUNT_FILE = Path.home() / ".config/optiplex-now/owner-music-host.json"
MAX_ACCOUNT = 4096


def read_owner_music_account(path=ACCOUNT_FILE):
    path = Path(path)
    directory = path.parent
    if directory.is_symlink() or not directory.is_dir():
        raise PolicyError("Music host account configuration is unavailable")
    fd=os.open(path,os.O_RDONLY|getattr(os,"O_NOFOLLOW",0))
    try:
        info=os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid!=os.geteuid()
                or stat.S_IMODE(info.st_mode)!=0o600 or info.st_nlink!=1
                or info.st_size>MAX_ACCOUNT):
            raise PolicyError("Unsafe Music owner account configuration")
        raw=os.read(fd,MAX_ACCOUNT+1)
    finally:
        os.close(fd)
    if len(raw)>MAX_ACCOUNT:
        raise PolicyError("Music owner account configuration too large")
    try:
        data=json.loads(raw)
    except (ValueError,UnicodeError):
        raise PolicyError("Invalid Music owner account configuration") from None
    if (not isinstance(data,dict) or set(data)!={
            "version","base_url","owner_principal_id","username","password"}
            or type(data["version"]) is not int or data["version"]!=1
            or any(not isinstance(data[k],str) or len(data[k])>2048
                   for k in ("base_url","owner_principal_id","username","password"))
            or not data["password"]):
        raise PolicyError("Invalid Music owner account configuration")
    return {k:data[k] for k in (
        "base_url","owner_principal_id","username","password")}


def issue_ssh_music_access(*, request, verified_client_id, config, wolf_api,
                           host_approved, account_reader=read_owner_music_account,
                           provision=issue_approved_music_access):
    """One exact restricted action; no remotely specified target/server/user.

    The host's existing Games approval configuration and a distinct explicit
    Music grant are BOTH required. A durable revoke record is committed before
    either credential is sent back on the restricted SSH channel.
    """
    if request!={"version":1,"action":"music_access"}:
        raise PolicyError("Unsupported owner Music request")
    if not host_approved:
        raise PolicyError("Owner host is not approved for Music access")
    store=OwnerStore(config["state_dir"])
    with store.locked() as fd:
        policy=store.read(fd)
        if policy is None:
            raise PolicyError("NOW owner policy not yet configured")
        paired=wolf_api("GET","/api/v1/clients")
        binding=resolve_music(policy,verified_client_id,paired)
        if get_device_locked(fd,verified_client_id) is not None:
            raise PolicyError("Music device already provisioned; revoke before reissuing")
        account=account_reader()
        result=provision(
            policy,verified_client_id,paired,host_account=account,
            record_grants=lambda record: record_issued_locked(
                fd,record,expected_host_id=binding["host_id"]))
        # This result is secret-bearing. It MUST be returned exclusively to
        # the authenticated restricted-SSH client, never diagnostic logs.
        if (not isinstance(result,dict) or
                set(result)!={"app_password","rest_token"}):
            raise ProvisionError("Invalid newly issued Music credentials")
        return {"success":True,"service":"music","credentials":result}



def revoke_owner_music_device(*, client_id, state_dir, confirmed=False,
                              account_reader=read_owner_music_account,
                              api_factory=DroppedNeedleAPI):
    """LOCAL host-owner-only upstream revoke, never a remotely callable action.

    Revoke the two DroppedNeedle credentials BEFORE removing NOW Music access.
    A failed or partial upstream revoke retains the ledger identifiers for
    retry; the owner is told cleanup remains outstanding.
    """
    if confirmed is not True:
        raise PolicyError("Local host-owner confirmation required")
    store=OwnerStore(state_dir)
    with store.locked() as fd:
        policy=store.read(fd)
        if policy is None:
            raise PolicyError("NOW owner policy unavailable")
        record=get_device_locked(fd,client_id)
        if record is None:
            raise PolicyError("Music device has no active credential record")
        if record["host_id"]!=policy["host_id"]:
            raise PolicyError("Music grant belongs to a different host")
        account=account_reader()
        if account.get("owner_principal_id")!=policy["principals"][0]["id"]:
            raise PolicyError("Music account does not match the NOW owner")
        api=api_factory(account["base_url"])
        standard, dn_user=api.login(account["username"],account["password"])
        if record["dn_user_id"]!=dn_user:
            raise ProvisionError("Music credential ownership changed")
        # Idempotent upstream delete permits recovering interrupted revocation.
        api.revoke(standard,app_id=record["app_password_id"],
                   session_id=record["companion_session_id"])

        # FIRST deny the authorization in the owner policy. If a disk write
        # fails now, the external credentials have already been revoked.
        for device in policy["devices"]:
            if device["client_id"] == client_id:
                if not device["revoked"] and "music" in device["services"]:
                    revoke_music(policy,client_id,upstream_revoked=True)
                elif "music" in device["services"]:
                    device["services"]=["games"]
                    from owner_access import validate
                    validate(policy)
                break
        store.write(fd,policy)
        # THEN erase the metadata. If this last write fails, no new Music
        # grant is possible and the stale IDs can be safely retried.
        remove_device_locked(fd,client_id)
        return {"success":True,"status":"music_revoked","client_id":client_id}
