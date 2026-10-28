"""Unit tests for non-privileged, local-only Jellyfin inventory."""
import io
from pathlib import Path
import sys
import unittest
from urllib.error import URLError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
from media_endpoint import LOOPBACK_INFO, inspect_local_jellyfin


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
