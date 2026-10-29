"""Owner-only download library destinations and explicit magnet enqueue.

Host-local adapter; the existing restricted owner device command MUST authorize
before calling any function. Only already-mounted writable Docker bind volumes
at /library/<slug> can be picked. No arbitrary host paths or shell commands
arrive from clients, and no media files are moved or reorganized.
"""
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
    for entry in qbit.get("Mounts",[]):
        if not isinstance(entry,dict) or entry.get("Type")!="bind" or entry.get("RW") is not True:
            continue
        container_path=entry.get("Destination")
        source=entry.get("Source")
        if not isinstance(container_path,str) or not isinstance(source,str):
            continue
        found=re.fullmatch(r"/library/([a-z][a-z0-9_-]{0,31})",container_path)
        if not found or not os.path.isabs(source) or source=="/" or not os.path.isdir(source):
            continue
        # A bind mount is administrator-owned configuration. Reject symlinked
        # root aliases and the main OS/system directories, not just / itself.
        resolved=os.path.realpath(source)
        if (resolved!=source or os.path.islink(source)
                or resolved in ("/etc","/root","/home","/usr","/var",
                                "/dev","/sys","/proc","/run","/boot")):
            continue
        slug=found.group(1)
        if slug in roots:
            raise DestinationError("Duplicate library destination root")
        roots[slug]={"source":source,"target":container_path}
    if not roots or len(roots)>12:
        raise DestinationError("No approved writable media library mounts")
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
    return {"roots":[{"id":name,"label":name.replace("_"," ").title()}
                     for name in sorted(mounts)]}

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
    command=["docker","exec",gateway,"wget","-q","-T","5","-O","-",
             "--post-data="+form,url]
    try:
        result=runner(command,capture_output=True,timeout=8,check=False)
    except (OSError,subprocess.TimeoutExpired) as exc:
        raise DestinationError("Downloader add unavailable") from exc
    if result.returncode or result.stdout.strip()!=b"Ok.":
        raise DestinationError("Downloader did not accept the torrent")
    return {"status":"submitted"}
