"""Regression gates for opt-in SubDuet pilot. No Docker or server needed."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / "tools" / "bilingual_subtitles_pilot.py"
spec = importlib.util.spec_from_file_location("bilingual_subtitles_pilot", SOURCE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class BilingualSubtitlePilotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.media = self.root / "sample folder"
        self.media.mkdir()
        (self.media / "Foreign Film.mkv").write_bytes(b"test-media-placeholder")
        (self.media / "Foreign Film.en.srt").write_text(
            "1\n00:00:00,000 --> 00:00:02,000\nHello\n", encoding="utf-8"
        )
        (self.media / "Foreign Film.ja.srt").write_text(
            "1\n00:00:00,000 --> 00:00:02,000\nこんにちは\n", encoding="utf-8"
        )

    def test_finds_paired_tracks(self):
        self.assertEqual(mod.find_sample(self.media), "Foreign Film.mkv")

    def test_rejects_missing_ja(self):
        (self.media / "Foreign Film.ja.srt").unlink()
        with self.assertRaisesRegex(ValueError, "matching"):
            mod.find_sample(self.media)

    def test_rejects_symlinked_subtitle(self):
        ja = self.media / "Foreign Film.ja.srt"
        ja.unlink()
        ja.symlink_to(self.media / "Foreign Film.en.srt")
        with self.assertRaises(ValueError):
            mod.find_sample(self.media)

    def test_build_env_offline_defaults(self):
        env = mod.build_env(self.media, 1000, 1000, "test-token")
        for flag in ("PAIRCUE_TRANSLATION_ENABLED", "PAIRCUE_TRANSCRIPTION_ENABLED",
                     "PAIRCUE_SUBTITLE_DOWNLOAD_ENABLED", "PAIRCUE_SYNC_ENABLED"):
            self.assertIn(f'{flag}="false"', env)
        self.assertIn('PAIRCUE_TARGET_LANGUAGE="ja"', env)
        self.assertIn('PAIRCUE_SOURCE_LANGUAGE="en"', env)
        self.assertIn('MEDIA_PATH="'+str(self.media)+'"', env)
        self.assertNotIn("JELLYFIN", env)

    @patch.object(mod.os, "geteuid", return_value=1000)
    @patch.object(mod.os, "getuid", return_value=1000)
    @patch.object(mod.os, "getgid", return_value=1000)
    def test_prepare_is_private_and_non_destructive(self, *_):
        workspace = self.root / "pilot"
        work, sample = mod.prepare(str(self.media), str(workspace))
        self.assertEqual(sample, "Foreign Film.mkv")
        self.assertEqual((work / "paircue.env").stat().st_mode & 0o777, 0o600)
        self.assertIn("127.0.0.1:9294:9292", (work / "compose.yaml").read_text())
        self.assertFalse((self.media / "Foreign Film.mul.srt").exists())
        with self.assertRaisesRegex(ValueError, "already exists"):
            mod.prepare(str(self.media), str(workspace))

    def test_rejects_parent_and_unsafe_path(self):
        with self.assertRaises(ValueError):
            mod.clean_path("a\nMEDIA_PATH=/secret", name="media-root")
        with patch.object(mod.os, "geteuid", return_value=1000):
            with self.assertRaisesRegex(ValueError, "contain"):
                mod.prepare(str(self.media), str(self.root))

    def test_compose_security_limits(self):
        self.assertIn("no-new-privileges:true", mod.COMPOSE)
        self.assertIn("cap_drop:", mod.COMPOSE)
        self.assertIn("read_only: true", mod.COMPOSE)
        self.assertNotIn('network_mode: "service:gluetun"', mod.COMPOSE)


if __name__ == "__main__":
    unittest.main()
