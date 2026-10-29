#!/usr/bin/env python3
"""Owner-only, bounded library browser / explicit torrent Add transport.

Never stores credentials, uses a shell, or connects directly to qBittorrent.
One restricted SSH request per user action; the host verifies each selection.
"""
import json
from pathlib import Path
import re
import subprocess
import sys

KEY = Path.home() / ".local/share/optiplex-now/games-client/id_ed25519"
ROOT = re.compile(r"[a-z][a-z0-9_-]{0,31}\Z")
HOST = re.compile(r"[A-Za-z0-9.:-]{1,253}\Z")
USER = re.compile(r"[a-zA-Z_][a-zA-Z0-9_-]{0,31}\Z")

def safe_text(value, limit=160):
    if (not isinstance(value,str) or not value or len(value)>limit or
        any(ord(c)<32 or ord(c)==127 for c in value)):
        raise ValueError("Invalid folder metadata")
    return value

def relative(value):
    if not isinstance(value,str) or len(value)>512:
        raise ValueError("Invalid destination folder")
    if value and (len(value.split("/"))>12 or
       any(not p or p in (".","..") or len(p)>160 or
           any(ord(c)<32 or ord(c)==127 for c in p)
           for p in value.split("/"))):
        raise ValueError("Invalid destination folder")
    return value

def present(action,data):
    if not isinstance(data,dict) or data.get("success") is not True:
        raise ValueError("Owner service denied the operation")
    if action=="manage":
        if (data.get("status")!="submitted" or
                data.get("operation") not in ("pause","resume","reannounce","recheck","remove")):
            raise ValueError("Torrent operation was not accepted")
        return "MANAGED"
    if action=="add":
        if data.get("status")!="submitted":
            raise ValueError("Downloader did not accept the torrent")
        return "SUBMITTED"
    if data.get("service")!="qbittorrent":
        raise ValueError("Not an approved downloader response")
    if action=="roots":
        entries=data.get("roots")
        if not isinstance(entries,list) or len(entries)>12:
            raise ValueError("Unusable destination roots")
        lines=["ROOTS"]
        for item in entries:
            if (not isinstance(item,dict) or
                    not isinstance(item.get("id"),str) or
                    not ROOT.fullmatch(item["id"])):
                raise ValueError("Invalid destination root")
            label=safe_text(item.get("label"))
            lines.append(f"ROOT\t{item['id']}\t{label}")
        return "\n".join(lines)
    if action=="browse":
        root=data.get("root")
        if not isinstance(root,str) or not ROOT.fullmatch(root):
            raise ValueError("Invalid destination root")
        path=relative(data.get("relative"))
        folders=data.get("folders")
        if not isinstance(folders,list) or len(folders)>100:
            raise ValueError("Invalid destination folder listing")
        return "\n".join([f"FOLDERS\t{root}\t{path}"]+
                         [f"FOLDER\t{safe_text(name)}" for name in folders])
    raise ValueError("Unsupported operation")

def fetch(host,user,action,root=None,path=None,magnet=None,*,runner=subprocess.run):
    if (not isinstance(host,str) or not HOST.fullmatch(host) or
        host.startswith("-") or not isinstance(user,str) or
        not USER.fullmatch(user) or not KEY.is_file()):
        raise ValueError("Not an enrolled NOW owner device")
    request={"version":1,"action":{
        "roots":"downloads_roots","browse":"downloads_browse",
        "add":"downloads_add","manage":"downloads_manage"}.get(action)}
    if request["action"] is None:
        raise ValueError("Invalid download action")
    if action=="manage":
        if (root not in ("pause","resume","reannounce","recheck","remove") or
                not isinstance(path,str) or
                not re.fullmatch(r"[0-9a-fA-F]{40}(?:[0-9a-fA-F]{24})?",path)):
            raise ValueError("Invalid torrent operation")
        request.update(operation=root,torrent_hash=path.lower())
    elif action!="roots":
        if not isinstance(root,str) or not ROOT.fullmatch(root):
            raise ValueError("Invalid library root")
        request.update(root=root,relative=relative(path))
        if action=="add":
            if (not isinstance(magnet,str) or not 10<=len(magnet)<=1024 or
                not magnet.startswith("magnet:?xt=urn:bt") or
                any(ord(c)<33 or ord(c)>126 for c in magnet)):
                raise ValueError("Invalid magnet")
            request["magnet"]=magnet
    payload=(json.dumps(request,ensure_ascii=False,separators=(",",":"))+"\n").encode()
    if len(payload)>2047:
        raise ValueError("Request too large")
    argv=["ssh","-F","/dev/null","-T","-i",str(KEY),
          "-o","IdentitiesOnly=yes","-o","BatchMode=yes",
          "-o","StrictHostKeyChecking=yes","-o","ConnectTimeout=6",
          f"{user}@{host}"]
    output=runner(argv,input=payload,stdout=subprocess.PIPE,
                  stderr=subprocess.DEVNULL,timeout=25,check=False)
    if (output.returncode or not isinstance(output.stdout,bytes) or
            len(output.stdout)>32768):
        raise ValueError("Approved host operation failed")
    try:
        return present(action,json.loads(output.stdout))
    except (ValueError,UnicodeDecodeError) as exc:
        raise ValueError("Unusable host response") from exc

if __name__=="__main__":
    try:
        args=sys.argv[1:]
        if len(args)<3 or args[2] not in ("roots","browse","add","manage") or (
            (args[2]=="roots" and len(args)!=3) or
            (args[2]=="browse" and len(args)!=5) or
            (args[2]=="add" and len(args)!=6) or
            (args[2]=="manage" and len(args)!=5)):
            raise ValueError("Expected owner host, action and checked selection")
        print(fetch(args[0],args[1],args[2],
                    *(args[3:]+[None]*(3-len(args[3:])))))
    except (ValueError,OSError,subprocess.SubprocessError):
        print("Owner download request unavailable.",file=sys.stderr)
        sys.exit(1)
