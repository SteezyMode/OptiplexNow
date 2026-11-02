"""Device keyring tests without reading any real login keyring or secrets."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
spec = importlib.util.spec_from_file_location("music_keyring", ROOT / "src" / "music_keyring.py")
music = importlib.util.module_from_spec(spec)
spec.loader.exec_module(music)


class FakeSecret:
    COLLECTION_DEFAULT = "default"
    cache = {}
    @classmethod
    def password_lookup_sync(cls, schema, attributes, cancellable):
        return cls.cache.get(attributes["server"])
    @classmethod
    def password_store_sync(cls, schema, attributes, collection, label, value, cancellable):
        assert collection == "default" and "Music" in label
        cls.cache[attributes["server"]] = value
        return True
    @classmethod
    def password_clear_sync(cls, schema, attributes, cancellable):
        cls.cache.pop(attributes["server"], None)
        return True


def fake_provider():
    return FakeSecret, object()


class MusicKeyringTests(unittest.TestCase):
    def setUp(self):
        FakeSecret.cache.clear()
        self.server = "http://100.121.156.34:8688"

    def test_first_connect_is_saved_and_next_lookup_has_same_credentials(self):
        self.assertIsNone(music.vault("lookup", self.server, provider=fake_provider))
        form = "api_key=unpredictable+key%2Bv1&username=listener"
        self.assertEqual(music.vault("store", self.server, form, fake_provider), "saved")
        self.assertEqual(music.vault("lookup", self.server, provider=fake_provider),
                         "api_key=unpredictable+key%2Bv1&username=listener")
        self.assertEqual(music.vault("clear", self.server, provider=fake_provider), "cleared")
        self.assertIsNone(music.vault("lookup", self.server, provider=fake_provider))

    def test_key_does_not_cross_server_boundaries(self):
        music.vault("store", self.server, "api_key=token&username=foo", fake_provider)
        self.assertIsNone(music.vault(
            "lookup", "http://100.121.156.34:8787", provider=fake_provider
        ))
        self.assertIsNone(music.vault(
            "lookup", "https://music.example.test", provider=fake_provider
        ))
        self.assertIsNone(music.vault(
            "lookup", self.server + "/other", provider=fake_provider
        ))

    def test_bad_passwords_never_get_stored(self):
        for form in ("", "foo=secret&username=user", "api_key=&username=user",
                     "api_key=ok&username=user&extra=secret", "api_key=a&api_key=b&username=u",
                     "api_key=a", "api_key=hello%0Aworld&username=u"):
            with self.subTest(form=form), self.assertRaises(music.VaultError):
                music.vault("store", self.server, form, fake_provider)
        self.assertEqual(FakeSecret.cache, {})

    def test_url_requirements_match_stream_transport(self):
        for url in ("http://8.8.8.8", "http://public.example.test",
                    "http://user:pass@127.0.0.1:8688",
                    "https://example.test/?password=123",
                    "file:///tmp/secret"):
            with self.subTest(url=url), self.assertRaises(music.VaultError):
                music.vault("lookup", url, provider=fake_provider)

    def test_keyring_errors_cannot_echo_secret(self):
        class BrokenSecret:
            @staticmethod
            def password_store_sync(*args):
                raise RuntimeError("leaked api_key=highly_secret_value")
        def broken():
            return BrokenSecret, object()
        with self.assertRaises(music.VaultError) as cm:
            music.vault("store", self.server,
                        "api_key=highly_secret_value&username=u", broken)
        self.assertNotIn("highly_secret_value", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
