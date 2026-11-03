"""Network-free checks for the read-only source benchmark."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "source_audit", ROOT / "tools" / "audit_torrent_sources.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SourceAuditTests(unittest.TestCase):
    def test_source_allowlist_avoids_unexpected_hosts(self):
        for kind in ("TorrentsCSV", "TorrentClaw", "API Bay", "EZTV API"):
            self.assertTrue(module.source_url(kind, "test").startswith("https://"))
        with self.assertRaises(ValueError):
            module.source_url("Untrusted", "test")

    def test_api_bay_ignores_empty_sentinel(self):
        self.assertEqual(module.title_entries("API Bay", [
            {"name": "No results returned", "added": "0"}]), [])

    def test_claw_nested_torrents_preserve_titles(self):
        self.assertEqual(module.title_entries("TorrentClaw", {
            "results": [{"title": "Show", "torrents": [
                {"rawTitle": "South.Park.S29E04", "uploadedAt": "2026-11-01T00:00:00Z"}]}]
        })[0][0], "South.Park.S29E04")

    def test_episode_matching_avoids_other_seasons(self):
        self.assertTrue(module.EPISODE_RE.search("South.Park.S29E04.1080p"))
        self.assertFalse(module.EPISODE_RE.search("South.Park.S29E03.1080p"))

    def test_timestamp_handles_invalid_input(self):
        self.assertIsNone(module.timestamp(None))
        self.assertIsNone(module.timestamp(True))
        self.assertIsNone(module.timestamp("0"))
        self.assertEqual(module.timestamp(1793491200).year, 2026)


if __name__ == "__main__":
    unittest.main()
