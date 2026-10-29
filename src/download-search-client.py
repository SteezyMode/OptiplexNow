#!/usr/bin/env python3
"""Sanitized owner-bound NOW search transport; no downloader action or admin URL."""
import json
from pathlib import Path
import re
import subprocess
import sys

KEY = Path.home() / ".local/share/optiplex-now/games-client/id_ed25519"
MAX_RESPONSE = 40000
MAX_RESULTS = 20

def valid_host(s):
    return (isinstance(s, str) and
            bool(re.fullmatch(r"[A-Za-z0-9.:-]{1,253}", s)) and
            not s.startswith("-"))

def valid_user(s):
    return isinstance(s, str) and bool(re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_-]{0,31}", s))

def _sanitize_text(value):
    if not isinstance(value, str) or not value or len(value)>160:
        raise ValueError("Unusable result name")
    result = "".join(c if c.isprintable() and c not in "\t\r\n" else " "
                     for c in value)
    if not result.strip():
        raise ValueError("Empty result name")
    return result

def present(response):
    if (not isinstance(response, dict) or response.get("success") is not True
            or response.get("service")!="qbittorrent"
            or response.get("status") not in ("Running","Stopped")
            or type(response.get("partial")) is not bool
            or type(response.get("total")) is not int
            or not 0 <= response["total"] <= 1000000):
        raise ValueError("Invalid authorized search response")
    items=response.get("results")
    if not isinstance(items, list) or len(items)>MAX_RESULTS:
        raise ValueError("Invalid search result collection")
    lines=[f"SEARCH\t{int(response['partial'])}\t{response['total']}"]
    for item in items:
        if not isinstance(item,dict):
            raise ValueError("Invalid search result")
        size=item.get("bytes")
        seeds=item.get("seeders")
        can_add=item.get("can_add")
        magnet=item.get("magnet")
        if (type(size) is not int or not -1 <= size <= 2**63-1
                or type(seeds) is not int or not -1 <= seeds <= 2**31-1
                or type(can_add) is not bool
                or not isinstance(magnet, (type(None),str))
                or bool(magnet) != can_add):
            raise ValueError("Invalid search result fields")
        # The magnet remains local for the owner's explicit Add click.
        safe_magnet = magnet if can_add else "-"
        if can_add and (len(safe_magnet)>1024 or any(
                ord(c)<33 or ord(c)>126 for c in safe_magnet)):
            raise ValueError("Invalid magnet field")
        lines.append(f"RESULT\t{size}\t{seeds}\t{int(can_add)}\t{_sanitize_text(item.get('name'))}\t{safe_magnet}")
    return "\n".join(lines)

def fetch(host, user, query, *, runner=subprocess.run):
    if not valid_host(host) or not valid_user(user) or not KEY.is_file():
        raise ValueError("Approved NOW host or device unavailable")
    if (not isinstance(query,str) or not 2 <= len(query.strip()) <= 96
            or any(ord(c)<32 or ord(c)==127 for c in query)):
        raise ValueError("Invalid search phrase")
    request=(json.dumps({"version":1,"action":"downloads_search","query":query.strip()},
                        ensure_ascii=False,separators=(",",":"))+"\n").encode("utf-8")
    if len(request)>767:
        raise ValueError("Oversized search request")
    cmd=["ssh","-F","/dev/null","-T","-i",str(KEY),
         "-o","IdentitiesOnly=yes","-o","BatchMode=yes",
         "-o","StrictHostKeyChecking=yes","-o","ConnectTimeout=6",
         f"{user}@{host}"]
    response=runner(cmd,input=request,stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,timeout=65,check=False)
    if (response.returncode or not isinstance(response.stdout,bytes)
            or len(response.stdout)>MAX_RESPONSE):
        raise ValueError("Owner search unavailable")
    try:
        data=json.loads(response.stdout)
    except (ValueError,UnicodeDecodeError) as exc:
        raise ValueError("Invalid owner search response") from exc
    return present(data)

if __name__=="__main__":
    try:
        if len(sys.argv)!=4:
            raise ValueError("Expected host, SSH user and search phrase")
        print(fetch(*sys.argv[1:4]))
    except (ValueError,OSError,subprocess.SubprocessError):
        print("Search unavailable. Check owner approval, VPN and search plugins.",
              file=sys.stderr)
        sys.exit(1)
