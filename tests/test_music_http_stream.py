"""Byte-range music playback transport: no live music account or file needed."""
import io
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
import threading
import unittest
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, urlopen
import wave

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from music_http_stream import MusicStreamGateway, RANGE_RE


def audio_sample():
    buf=io.BytesIO()
    with wave.open(buf,"wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(22050)
        audio.writeframes(b"\0\0" * 44100)
    return buf.getvalue()


class PrivateDN(BaseHTTPRequestHandler):
    sample=audio_sample()
    requests=[]
    def log_message(self,*args): pass
    def do_POST(self):
        fields=parse_qs(self.rfile.read(int(self.headers.get("Content-Length",0))).decode())
        rng=self.headers.get("Range")
        type(self).requests.append((self.path,fields,rng))
        if self.path!="/subsonic/rest/stream" or fields.get("apiKey")!=["secret-not-for-mpv"]:
            self.send_response(403);self.end_headers();return
        content=self.sample
        if rng:
            import re
            m=re.fullmatch(r"bytes=(\d+)-(\d*)",rng)
            if not m:
                self.send_response(416);self.end_headers();return
            start=int(m.group(1))
            end=min(int(m.group(2)) if m.group(2) else len(content)-1,len(content)-1)
            if start>len(content)-1 or end<start:
                self.send_response(416);self.end_headers();return
            content=content[start:end+1]
            self.send_response(206)
            self.send_header("Content-Range",f"bytes {start}-{end}/{len(self.sample)}")
        else:
            self.send_response(200)
        self.send_header("Content-Type","audio/wav")
        self.send_header("Accept-Ranges","bytes")
        self.send_header("Content-Length",str(len(content)))
        self.end_headers()
        self.wfile.write(content)


class GatewayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(("127.0.0.1",0),PrivateDN)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()
        cls.base=f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join(timeout=2)

    def setUp(self):
        PrivateDN.requests.clear()
        self.gateway=MusicStreamGateway(self.base,"secret-not-for-mpv","track-01")
        self.loopback=self.gateway.start()
        self.addCleanup(self.gateway.close)

    def test_complete_audio_never_exposes_upstream_key(self):
        self.assertTrue(self.loopback.startswith("http://127.0.0.1:"))
        self.assertNotIn("secret-not-for-mpv",self.loopback)
        self.assertNotIn(str(self.server.server_port),self.loopback)
        with urlopen(self.loopback, timeout=5) as resp:
            self.assertEqual(resp.status,200)
            self.assertEqual(resp.read(),PrivateDN.sample)
            self.assertEqual(resp.headers.get("Accept-Ranges"),"bytes")
        path,fields,rng=PrivateDN.requests[-1]
        self.assertEqual(path,"/subsonic/rest/stream")
        self.assertEqual(fields["apiKey"],["secret-not-for-mpv"])
        self.assertIsNone(rng)

    def test_loopback_byte_ranges_seek_without_transcoding(self):
        req=Request(self.loopback,headers={"Range":"bytes=16-63"})
        with urlopen(req,timeout=5) as resp:
            self.assertEqual(resp.status,206)
            self.assertEqual(resp.read(),PrivateDN.sample[16:64])
            self.assertEqual(resp.headers["Content-Range"],
                             f"bytes 16-63/{len(PrivateDN.sample)}")
        self.assertEqual(PrivateDN.requests[-1][2],"bytes=16-63")
        self.assertEqual(PrivateDN.requests[-1][1]["format"],["raw"])
        head=Request(self.loopback,method="HEAD")
        with urlopen(head,timeout=5) as resp:
            self.assertEqual(resp.headers["Content-Length"],str(len(PrivateDN.sample)))
            self.assertEqual(resp.read(),b"")

    def test_no_wrong_path_or_arbitrary_methods_or_ranges(self):
        p=urlsplit(self.loopback)
        guess=f"{p.scheme}://{p.netloc}/stream/not-the-secret"
        with self.assertRaises(HTTPError) as ctx:
            urlopen(guess,timeout=4)
        self.assertEqual(ctx.exception.code,404)
        with self.assertRaises(HTTPError) as ctx:
            urlopen(Request(self.loopback,headers={"Range":"bytes=0-1,4-5"}),timeout=4)
        self.assertEqual(ctx.exception.code,416)
        with self.assertRaises(HTTPError) as ctx:
            urlopen(Request(self.loopback,data=b"fake",method="POST"),timeout=4)
        self.assertEqual(ctx.exception.code,501)
        self.assertEqual(PrivateDN.requests,[])

    def test_invalid_ranges_rejected_before_upstream_contact(self):
        for range_value in ("bytes=-100","bytes=000-5",
                            "bytes=1-2,4-6","bytes=922337203685477580800-"):
            with self.subTest(range_value=range_value),self.assertRaises(HTTPError):
                urlopen(Request(self.loopback,headers={"Range":range_value}),timeout=3)
        self.assertEqual(PrivateDN.requests,[])
        self.assertTrue(RANGE_RE.fullmatch("bytes=0-100"))

    def test_gateway_clears_auth_and_stops_accepting_after_close(self):
        self.gateway.close()
        self.assertEqual(self.gateway.auth,{})
        with self.assertRaises(Exception):
            urlopen(self.loopback,timeout=1)


if __name__=="__main__":
    unittest.main()
