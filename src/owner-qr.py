"""Owner phone QR rendering with strict tailnet-only approval URL validation.

No third-party QR generator site is contacted. The six-digit code stays in a
URL fragment, which browsers do not send in an HTTP request to the host.
"""
import ipaddress
import re
import subprocess

HEX32 = re.compile(r"[0-9a-f]{32}\Z")
CODE = re.compile(r"[0-9]{6}\Z")

def approval_url(host, request_id, code):
    ip = ipaddress.IPv4Address(host)
    if (ip not in ipaddress.ip_network("100.64.0.0/10")
            or str(ip) == "100.100.100.100"
            or not isinstance(request_id, str)
            or not HEX32.fullmatch(request_id)
            or not isinstance(code, str)
            or not CODE.fullmatch(code)):
        raise ValueError("QR requires a pinned Tailnet host and staged request")
    return "http://" + str(ip) + ":18793/owner/approve/" + request_id + "#" + code

def qr_png(url, *, runner=subprocess.run):
    if not isinstance(url, str) or len(url) > 180:
        raise ValueError("Invalid QR data")
    # qrencode reads from stdin, so the short-lived code is not in process args.
    proc = runner(["qrencode", "-t", "PNG", "-s", "5", "-m", "2", "-o", "-"],
                  input=url.encode("ascii"), stdout=subprocess.PIPE,
                  stderr=subprocess.DEVNULL, timeout=5, check=True)
    if not proc.stdout.startswith(b"\x89PNG\r\n\x1a\n") or len(proc.stdout)>131072:
        raise ValueError("Invalid QR image")
    return proc.stdout
