"""Existing DroppedNeedle owner linking is opt-in and never resets an account."""
import sys
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch, MagicMock

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"src"),str(ROOT/"server")]
from music_link_existing import _host_url, link_existing
from music_device_provision import ProvisionError
from owner_access import PolicyError


class ExistingOwnerLinkTests(TestCase):
    def test_refuses_external_plain_http(self):
        for address in ("http://example.com:8688", "http://8.8.8.8:8688",
                        "http://user:pass@127.0.0.1:8688",
                        "http://127.0.0.1:8688/path"):
            with self.subTest(address=address), self.assertRaises(ProvisionError):
                _host_url(address)

    def test_loopback_is_allowed(self):
        self.assertEqual(_host_url("http://127.0.0.1:8688/"),
                         "http://127.0.0.1:8688")

    def test_existing_account_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"owner-music-host.json"
            path.write_text("protected")
            store=MagicMock()
            store.locked.return_value.__enter__.return_value=4
            store.read.return_value={"principals":[{"id":"owner-id","role":"owner"}]}
            with patch("music_link_existing._read_private_config",return_value={
                    "state_dir":temp,"enabled":True,"legacy_links_reviewed":True}), \\
                 patch("music_link_existing.OwnerStore",return_value=store), \\
                 patch("music_link_existing._private_config_dir"):
                with self.assertRaises(PolicyError):
                    link_existing(url="http://127.0.0.1:8688",
                                  username="user",password="private",
                                  account_path=path)
            self.assertEqual(path.read_text(),"protected")

    def test_fails_closed_when_droppedneedle_not_initialized(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"owner-music-host.json"
            store=MagicMock()
            store.locked.return_value.__enter__.return_value=4
            store.read.return_value={"principals":[{"id":"owner-id","role":"owner"}]}
            api=MagicMock()
            api.call.return_value={"required":True}
            with patch("music_link_existing._read_private_config",return_value={
                    "state_dir":temp,"enabled":True,"legacy_links_reviewed":True}), \\
                 patch("music_link_existing.OwnerStore",return_value=store), \\
                 patch("music_link_existing.DroppedNeedleAPI",return_value=api):
                with self.assertRaises(ProvisionError):
                    link_existing(url="http://127.0.0.1:8688",
                                  username="user",password="private",
                                  account_path=path)
            api.login.assert_not_called()
            self.assertFalse(path.exists())
