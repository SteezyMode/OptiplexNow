"""Small owner-only phone confirmation page for a staged device.

The URL fragment carries the six-digit enrollment code and is never transmitted
with the GET. The server independently authenticates the requesting phone over
Tailscale before returning the page and before handling the existing approved
JSON mutation. The QR is NOT a substitute for Wolf identity review.
"""
import html
import re
import secrets

PAGE_PREFIX = "/owner/approve/"
REQUEST_ID = re.compile(r"[0-9a-f]{32}\Z")
FINGERPRINT = re.compile(r"[0-9a-f]{20}\Z")

def parse_page_request(path):
    if not isinstance(path, str) or not path.startswith(PAGE_PREFIX):
        raise ValueError("Not an owner approval page")
    request_id = path[len(PAGE_PREFIX):]
    if not REQUEST_ID.fullmatch(request_id):
        raise ValueError("Invalid owner approval request URL")
    return request_id

def render_page(request_id, fingerprint, seconds_remaining, *, nonce=None):
    if (not REQUEST_ID.fullmatch(request_id or "")
            or not FINGERPRINT.fullmatch(fingerprint or "")
            or type(seconds_remaining) is not int
            or not 0 < seconds_remaining <= 900):
        raise ValueError("Invalid host enrollment metadata")
    nonce = nonce or secrets.token_urlsafe(24)
    if not re.fullmatch(r"[A-Za-z0-9_-]{16,64}", nonce):
        raise ValueError("Invalid CSP nonce")
    # Request ID and fingerprint are verified host-side, never query parameters.
    page = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>OptiPlex NOW — Owner approval</title>
<style nonce="@@NONCE@@">
*{box-sizing:border-box}body{font:16px system-ui,sans-serif;max-width:460px;margin:24px auto;padding:0 18px;background:#101111;color:#ece8e0}
h1{font-size:24px}p{line-height:1.45}small{color:#ccc}.info{padding:14px;border:1px solid #555;border-radius:6px;overflow-wrap:anywhere}
code{color:#e8c28f}button{background:#c47d65;color:#101111;border:0;border-radius:5px;padding:15px;font-size:18px;font-weight:700;width:100%;margin-top:14px}
button:disabled{background:#6d6f69;color:#ddd}.warn{color:#e8c28f}#status{min-height:3em}
</style></head><body>
<h1>Approve this device</h1>
<p>Use only on <strong>your own phone</strong> connected to your owner's Tailscale account. Confirm the code and key fingerprint match the requesting computer.</p>
<div class="info">
<p>Device verification code: <strong id="code" class="warn">—</strong></p>
<p>Restricted key fingerprint: <code>@@FINGERPRINT@@</code></p>
<p>Wolf device observed by host: <code id="client">Checking…</code></p>
<small>Request expires in at most @@SECONDS@@ seconds. Only the unique active paired Wolf UI session can be approved. No Steam session can be running during review.</small>
</div>
<p id="status" role="status">Checking the live Wolf session…</p>
<button id="approve" disabled>Approve owner device</button>
<button id="refresh" type="button">Check Wolf session again</button>
<p><small>Approval grants this client only the existing restricted Games/Downloads credential, not an administrator shell. No active-session identity: no approval.</small></p>
<script nonce="@@NONCE@@">
"use strict";
(function(){
  var requestId="@@REQUEST@@";
  var code=window.location.hash.slice(1);
  window.history.replaceState(null,"",window.location.pathname);
  var approve=document.getElementById("approve");
  var status=document.getElementById("status");
  var wolf=document.getElementById("client");
  var candidate=null, busy=false;
  document.getElementById("code").textContent=/^[0-9]{6}$/.test(code)?code:"INVALID";
  function message(value){status.textContent=value;}
  async function inspect(){
    candidate=null;approve.disabled=true;
    if(!/^[0-9]{6}$/.test(code)){message("QR code is incomplete. Rescan it on the requesting device.");return;}
    message("Checking for one paired Wolf UI session…");
    try {
      var resp=await fetch("/v1/owner/enrollment/wolf-candidate/"+requestId,{cache:"no-store",credentials:"omit"});
      var data=await resp.json();
      if(!resp.ok||data.success!==true||!/^[0-9]{1,20}$/.test(data.wolf_client_id)){
        wolf.textContent="No unique eligible session";
        message("No matching device. Stream Wolf UI using the same network path as this computer's enrollment, then check again.");
        return;
      }
      candidate=data.wolf_client_id;
      wolf.textContent=candidate;
      message("Compare the six-digit code and fingerprint on your computer. Approve only if this is your Wolf session.");
      approve.disabled=false;
    }catch(error){wolf.textContent="Unavailable";message("The host cannot verify Wolf. Check Tailscale and retry.");}
  }
  approve.addEventListener("click",async function(){
    if(busy||!candidate||!/^[0-9]{6}$/.test(code))return;
    busy=true;approve.disabled=true;
    message("Asking the host to verify the Wolf session and approve the restricted device…");
    try{
      var resp=await fetch("/v1/owner/enrollment/approve",{
        method:"POST",cache:"no-store",credentials:"omit",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({request_id:requestId,code:code,wolf_client_id:candidate,confirmed:true})
      });
      var data=await resp.json();
      if(!resp.ok||data.success!==true||data.status!=="approved")throw Error("denied");
      message("Approved. Return to OptiPlex NOW on the requesting computer. Verify access there.");
      document.getElementById("refresh").disabled=true;code="";candidate=null;
    }catch(error){
      message("Approval denied or session changed. No permissions were granted; check the session again.");
      busy=false;
    }
  });
  document.getElementById("refresh").addEventListener("click",function(){if(!busy)inspect();});
  inspect();
})();
</script></body></html>"""
    return (page.replace("@@NONCE@@", nonce)
                .replace("@@REQUEST@@", html.escape(request_id, quote=True))
                .replace("@@FINGERPRINT@@", html.escape(fingerprint, quote=True))
                .replace("@@SECONDS@@", str(seconds_remaining))), nonce
