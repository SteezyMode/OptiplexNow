"""Local-only playback worker contract; no real host, account, or music needed."""
from __future__ import annotations

import importlib.util
import io
import os
import tempfile
from pathlib import Path
from unittest import mock
import unittest

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "src"))
spec = importlib.util.spec_from_file_location("music_player", ROOT / "src" / "music_player.py")
player = importlib.util.module_from_spec(spec)
spec.loader.exec_module(player)


class FakeSocket:
    sent = b""
    def __enter__(self): return self
    def __exit__(self, *unused): return None
    def settimeout(self, value): pass
    def connect(self, path): self.path=path
    def sendall(self, data): type(self).sent=data
    def recv(self, amount): return b'{"error":"success"}\n'


class MusicPlaybackContract(unittest.TestCase):
    def test_credentials_only_on_stdin(self):
        auth = player.read_auth(io.BytesIO(b"api_key=app%2Bsecret&username=listener\n"))
        self.assertEqual(auth, {"apiKey": "app+secret", "u": "listener"})
        for s in (b"", b"api_key=x&username=a", b"api_key=&username=x\n",
                  b"api_key=ok&username=x&extra=bad\n",
                  b"api_key=one&api_key=two&username=x\n",
                  b"api_key=a%0Ab&username=x\n"):
            with self.subTest(data=s), self.assertRaises(player.PlaybackError):
                player.read_auth(io.BytesIO(s))

    def test_mpv_pause_control_is_exactly_whitelisted(self):
        with mock.patch.object(player.socket, "socket", return_value=FakeSocket()):
            self.assertTrue(player.socket_command("/private/control.sock", True))
            self.assertEqual(FakeSocket.sent,
                b'{"command":["set_property","pause",true]}\n')
            self.assertTrue(player.socket_command("/private/control.sock", False))
            self.assertEqual(FakeSocket.sent,
                b'{"command":["set_property","pause",false]}\n')

    def test_mpv_commands_do_not_contain_keys_or_urls(self):
        content = (ROOT / "src" / "music_player.py").read_text()
        self.assertIn('stdin=subprocess.PIPE', content)
        self.assertIn('stdout=subprocess.DEVNULL', content)
        self.assertIn('stderr=subprocess.DEVNULL', content)
        self.assertIn('close_fds=True', content)
        self.assertIn('TemporaryDirectory(prefix="bruiser-music-"', content)
        self.assertIn('preexec_fn=_parent_exit_signal', content)
        self.assertIn('_post(server, "stream", auth, {"id": track_id, "format": "raw"})', content)
        self.assertIn('if action == "STOP":', content)
        self.assertIn('action not in ("PAUSE", "RESUME")', content)
        self.assertNotIn('apiKey=', content)
        self.assertNotIn('subprocess.run("', content)

    def test_mpv_is_not_launched_without_valid_auth(self):
        out=io.StringIO()
        with mock.patch.object(player.subprocess, "Popen") as mocked:
            code=player.run("http://127.0.0.1:8688", "song", io.BytesIO(b"bad\n"),
                            io.BytesIO(), out, mpv_binary="/bin/false")
        self.assertEqual(code, 2)
        self.assertIn("ERROR", out.getvalue())
        mocked.assert_not_called()

    def test_no_mpv_is_clear_failure(self):
        out=io.StringIO()
        with mock.patch.object(player.shutil, "which", return_value=None):
            code=player.run("http://127.0.0.1:8688", "song",
                            io.BytesIO(b"api_key=a&username=u\n"),
                            io.BytesIO(), out)
        self.assertEqual(code, 3)
        self.assertEqual(out.getvalue(), "ERROR\n")

    def test_no_proxy_or_redirect_in_shared_transport(self):
        content=(ROOT / "src" / "music_subsonic.py").read_text()
        self.assertIn("ProxyHandler({})", content)
        self.assertIn("DenyRedirects()", content)
        self.assertIn('method="POST"', content)


if __name__ == "__main__":
    unittest.main()
