"""Offline end-to-end Music smoke: fake Subsonic server -> worker -> real mpv null sink."""
import io
import os
import selectors
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs

PLAYER = Path(__file__).resolve().parents[1] / "src/music_player.py"

class Stream(BaseHTTPRequestHandler):
    requests = []
    def log_message(self, *args): pass
    def do_POST(self):
        raw=self.rfile.read(int(self.headers.get("Content-Length",0)))
        params=parse_qs(raw.decode())
        type(self).requests.append((self.path,params))
        if params.get("apiKey")!=["test-only"]:
            self.send_response(403)
            self.end_headers()
            return
        sound=io.BytesIO()
        with wave.open(sound,"wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(22050)
            audio.writeframes(b"\x00\x00" * 33075)
        data=sound.getvalue()
        header=self.headers.get("Range")
        if header:
            import re
            m=re.fullmatch(r"bytes=(\\d+)-(\\d*)",header)
            if not m:
                self.send_response(416);self.end_headers();return
            start=int(m.group(1))
            end=int(m.group(2)) if m.group(2) else len(data)-1
            if start>=len(data) or end<start:
                self.send_response(416);self.end_headers();return
            end=min(end,len(data)-1)
            self.send_response(206)
            self.send_header("Content-Range","bytes %d-%d/%d"%(start,end,len(data)))
            data=data[start:end+1]
        else:
            self.send_response(200)
        self.send_header("Content-Type","audio/wav")
        self.send_header("Accept-Ranges","bytes")
        self.send_header("Content-Length",str(len(data)))
        self.end_headers()
        self.wfile.write(data)

@unittest.skipUnless(shutil.which("mpv"),"real mpv required")
class PlaybackSmoke(unittest.TestCase):
    def test_local_stream_decodes_and_ends(self):
        server=ThreadingHTTPServer(("127.0.0.1",0),Stream)
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                wrapper=Path(tmp)/"mpv"
                wrapper.write_text('#!/bin/sh\nexec "'+shutil.which("mpv")+'" --ao=null "$@"\n')
                wrapper.chmod(0o700)
                env={**os.environ,"PATH":tmp+os.pathsep+os.environ.get("PATH","")}
                proc=subprocess.Popen(
                    [sys.executable,"-u",str(PLAYER),
                     "http://127.0.0.1:%s"%server.server_port,"track-1","75"],
                    stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,env=env)
                try:
                    proc.stdin.write(b"api_key=test-only&username=test\n")
                    proc.stdin.flush()
                    events=[]
                    with selectors.DefaultSelector() as sel:
                        sel.register(proc.stdout,selectors.EVENT_READ)
                        end=time.monotonic()+12
                        while time.monotonic()<end:
                            if sel.select(timeout=.2):
                                line=proc.stdout.readline()
                                if line: events.append(line.decode().strip())
                            if "ENDED" in events or "ERROR" in events or "STOPPED" in events:
                                break
                    self.assertIn("BUFFERING",events)
                    self.assertIn("PLAYING",events)
                    self.assertIn("ENDED",events)
                    self.assertNotIn("ERROR",events)
                    self.assertTrue(any(x.startswith("POSITION ") for x in events),
                                    "mpv must report real elapsed/duration")
                    self.assertEqual(proc.wait(timeout=2),0)
                    path,params=Stream.requests[-1]
                    self.assertEqual(path,"/subsonic/rest/stream")
                    self.assertEqual(params["apiKey"],["test-only"])
                    self.assertNotIn("test-only"," ".join(proc.args))
                finally:
                    if proc.poll() is None:
                        proc.terminate()
                        try: proc.wait(timeout=2)
                        except subprocess.TimeoutExpired:
                            proc.kill()
                            proc.wait(timeout=2)
                    proc.stdin.close()
                    proc.stdout.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
