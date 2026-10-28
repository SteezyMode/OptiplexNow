"""Unit tests for non-privileged, local-only Jellyfin inventory."""
import io
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
from threading import Thread
import unittest
from urllib.error import HTTPError, URLError
from urllib.request import Request

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
from media_endpoint import LOOPBACK_INFO, _local_urlopen, inspect_local_jellyfin


class Reply:
    status = 200
    def __init__(self, payload):
        self.body = io.BytesIO(payload)
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self, count):
        return self.body.read(count)


class MediaInventoryTests(unittest.TestCase):
    def test_only_fixed_local_endpoint_and_bounded_timeout(self):
        def open_request(request, timeout):
            self.assertEqual(request.full_url, LOOPBACK_INFO)
            self.assertEqual(timeout, 3)
            return Reply(b'{"Id":"a-server","ServerName":"My Library","ApiKey":"secret"}')
        self.assertEqual(inspect_local_jellyfin(opener=open_request),
                         {"service":"jellyfin","available":True,"name":"My Library",
                          "server_id":"a-server"})

    def test_never_reflect_secrets_or_untrusted_urls(self):
        payload = b'{"Id":"server","Url":"https://evil.invalid","Token":"SECRET"}'
        result = inspect_local_jellyfin(opener=lambda *a,**k: Reply(payload))
        self.assertNotIn("Url", result)
        self.assertNotIn("Token", result)
        self.assertEqual(result, {"service":"jellyfin","available":True,"server_id":"server"})

    def test_only_owner_approved_same_host_endpoint_is_published(self):
        import json
        import tempfile
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as base:
            config = Path(base) / "media-public-endpoint.json"
            probe = lambda *a, **k: Reply(b'{"Id":"our-jellyfin","ApiKey":"PRIVATE"}')
            entry = {"version":1,"scheme":"https","port":443,"base_path":"/jellyfin"}
            config.write_text(json.dumps(entry))
            config.chmod(0o600)
            with patch("media_endpoint.os.geteuid", return_value=config.stat().st_uid):
                actual = inspect_local_jellyfin(opener=probe, endpoint_path=config)
                self.assertEqual(actual, {
                    "service":"jellyfin", "available":True,
                    "server_id":"our-jellyfin",
                    "endpoint":{"scheme":"https","port":443,"base_path":"/jellyfin"}})
                for bad in (
                    {**entry,"base_path":"//evil"},
                    {**entry,"base_path":"/evil/path"},
                    {**entry,"scheme":"ftp"},
                    {**entry,"port":65536},
                    {**entry,"port":True},
                    {**entry,"hostname":"evil.invalid"},
                ):
                    config.write_text(json.dumps(bad))
                    config.chmod(0o600)
                    self.assertEqual(inspect_local_jellyfin(
                        opener=probe, endpoint_path=config),
                        {"service":"jellyfin", "available":False})
                config.write_text(json.dumps(entry))
                config.chmod(0o644)
                self.assertFalse(inspect_local_jellyfin(
                    opener=probe, endpoint_path=config)["available"])
                config.unlink()
                other = Path(base) / "outside"
                other.write_text(json.dumps(entry))
                other.chmod(0o600)
                config.symlink_to(other)
                self.assertFalse(inspect_local_jellyfin(
                    opener=probe, endpoint_path=config)["available"])

    def test_real_local_probe_never_follows_http_redirects(self):
        visited = []
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                visited.append(self.path)
                if self.path == "/first":
                    self.send_response(302)
                    self.send_header("Location", "/not-local-inventory")
                    self.end_headers()
                else:
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b'{"Id":"wrong"}')
            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        runner = Thread(target=server.serve_forever, daemon=True)
        runner.start()
        try:
            url = "http://127.0.0.1:%d/first" % server.server_port
            with self.assertRaises(HTTPError) as cm:
                with _local_urlopen(Request(url), timeout=2):
                    self.fail("Redirected local probe was accepted")
            self.assertEqual(cm.exception.code, 302)
            self.assertEqual(visited, ["/first"])
        finally:
            server.shutdown()
            server.server_close()
            runner.join(timeout=2)

    def test_unavailable_or_malformed_fails_closed(self):
        for response in (b'', b'[]', b'{"ServerName":"missing-id"}',
                         b'{"Id":32}', b'{"Id":"a"}' + b' ' * 9000):
            with self.subTest(response=response[:25]):
                self.assertFalse(inspect_local_jellyfin(
                    opener=lambda *a,**k: Reply(response))["available"])
        self.assertFalse(inspect_local_jellyfin(
            opener=lambda *a,**k: (_ for _ in ()).throw(
                URLError("unreachable")))["available"])

    def test_untrusted_id_content_and_redirects_cannot_be_published(self):
        for value in ("http://other-host/path", "../wrong", "a b",
                      "", "z" * 129):
            with self.subTest(value=value):
                payload = __import__("json").dumps({"Id": value}).encode()
                result = inspect_local_jellyfin(
                    opener=lambda *a, **k: Reply(payload))
                self.assertEqual(result, {"service":"jellyfin",
                                          "available": False})
        class Redirect(Reply):
            status = 302
        self.assertEqual(inspect_local_jellyfin(
            opener=lambda *a,**k: Redirect(b'{"Id":"valid"}')),
            {"service":"jellyfin","available":False})


if __name__ == "__main__":
    unittest.main()
