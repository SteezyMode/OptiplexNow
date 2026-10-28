"""Pure read-only existing-stack storage relationship tests. No Docker or file access."""
import contextlib
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))
import host_adoption
import host_services
import host_storage_review as storage


def record(image, sources):
    return {
        "Config": {"Image": image, "Env": ["VPN_PASSWORD=do-not-leak"]},
        "Mounts": [
            {"Type": "bind", "Source": source,
             "Destination": "/ignored", "RW": True}
            for source in sources],
    }


def pair(a="/mnt/media", b="/mnt/media"):
    return [
        record("jellyfin/jellyfin:10.11", [a]),
        record("lscr.io/linuxserver/qbittorrent:5", [b]),
    ]


class StorageReviewTests(unittest.TestCase):
    def check_no_leak(self, records, expected):
        result = storage.review(records)
        self.assertEqual(result["status"], expected)
        self.assertTrue(result["read_only"])
        self.assertTrue(result["candidate_only"])
        self.assertFalse(result["changes_performed"])
        self.assertFalse(result["may_manage_files"])
        self.assertFalse(result["may_change_mounts"])
        self.assertTrue(result["owner_confirmation_required"])
        serialized = json.dumps(result)
        for private in ("/mnt/media", "/mnt/videos", "/mnt/downloads",
                        "VPN_PASSWORD", "do-not-leak",
                        "jellyfin/jellyfin", "qbittorrent:5"):
            self.assertNotIn(private, serialized)
        return result

    def test_exact_and_nested_mounts_are_hints_not_authorization(self):
        self.check_no_leak(pair(), storage.SHARED)
        self.check_no_leak(
            pair("/mnt/media", "/mnt/media/downloads"), storage.NESTED)
        self.check_no_leak(
            pair("/mnt/media/movies", "/mnt/media"), storage.NESTED)

    def test_distinct_mounts_and_common_prefix_not_overlap(self):
        self.check_no_leak(
            pair("/mnt/videos", "/mnt/downloads"), storage.NO_OVERLAP)
        self.check_no_leak(
            pair("/mnt/media", "/mnt/media-other"), storage.NO_OVERLAP)

    def test_missing_ambiguous_or_unavailable_never_proves_shared(self):
        self.check_no_leak(None, storage.UNKNOWN)
        self.check_no_leak([], storage.UNKNOWN)
        self.check_no_leak([pair()[0]], storage.UNKNOWN)
        self.check_no_leak(
            pair() + [record("jellyfin/jellyfin:second", ["/mnt/videos"])],
            storage.UNKNOWN)
        self.check_no_leak(
            [record("jellyfin/jellyfin:10.11", []),
             record("lscr.io/linuxserver/qbittorrent:5", ["/mnt/media"])],
            storage.NO_MOUNTS)
        self.check_no_leak(pair() + [None], storage.UNKNOWN)

    def test_invalid_mount_metadata_fails_closed(self):
        for bad in (
            "/", "/mnt/../media", "/mnt//media", "/mnt/media/",
            "/mnt/media\nattack", "relative/path", "/mnt/" + "a" * 1024,
            42, None,
        ):
            with self.subTest(bad=bad):
                recs = pair()
                recs[0]["Mounts"][0]["Source"] = bad
                self.check_no_leak(recs, storage.UNKNOWN)
        recs = pair()
        recs[0]["Mounts"] = [{"Type": "bind", "Destination": "/foo"}]
        self.check_no_leak(recs, storage.UNKNOWN)
        recs = pair()
        recs[0]["Mounts"] = [None]
        self.check_no_leak(recs, storage.UNKNOWN)
        recs = pair()
        recs[0]["Mounts"] = [{}] * 33
        self.check_no_leak(recs, storage.UNKNOWN)

    def test_named_volumes_are_not_bind_mounts(self):
        recs = pair()
        recs[0]["Mounts"] = [{"Type": "volume", "Name": "secrets",
                              "Source": "/mnt/media", "Destination": "/media"}]
        self.check_no_leak(recs, storage.NO_MOUNTS)

    def test_host_review_uses_one_census_without_returning_paths(self):
        from test_host_services import fake_docker, record as fixture
        a, b, c, d = ("a" * 64, "b" * 64, "c" * 64, "d" * 64)
        records = [
            fixture(a, "ghcr.io/games-on-whales/wolf:stable"),
            fixture(b, "jellyfin/jellyfin:10.11"),
            fixture(c, "qmcgaw/gluetun:v3", name="/vpn", health="healthy"),
            fixture(d, "lscr.io/linuxserver/qbittorrent:5",
                    mode="container:vpnn", name="/qbit"),
        ]
        # The old fixture already has a shared /private/home/media bind.
        invoked = []
        real_assess = host_services.assess
        def census():
            invoked.append(1)
            return records
        output = io.StringIO()
        with patch.object(host_services, "docker_records", side_effect=census), \
             contextlib.redirect_stdout(output):
            self.assertEqual(host_adoption.main(), 0)
        self.assertEqual(len(invoked), 1)
        text = output.getvalue()
        self.assertIn("MEDIA / DOWNLOADS SHARED STORAGE:", text)
        self.assertIn(storage.SHARED, text)
        self.assertIn("FILE ACCESS / STORAGE MOUNT APPROVAL: NOT GRANTED", text)
        self.assertNotIn("/private/home/media", text)
        self.assertNotIn("/mnt/media", text)

    def test_unavailable_privileged_census_is_unknown_without_paths(self):
        from unittest.mock import patch
        output = io.StringIO()
        with patch.object(host_services, "docker_records",
                          side_effect=host_services.InventoryUnavailable("denied")), \
             contextlib.redirect_stdout(output):
            self.assertEqual(host_adoption.main(), 0)
        self.assertIn(storage.UNKNOWN, output.getvalue())
        self.assertIn("NOT GRANTED", output.getvalue())


if __name__ == "__main__":
    unittest.main()
