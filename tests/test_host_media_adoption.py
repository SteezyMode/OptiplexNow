"""Isolated host Videos existing-Jellyfin adoption; never touches real host."""
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))
import host_media_adoption as adoption


class Reply:
    status = 200
    def __init__(self, data=b'{"Id":"our-jellyfin","ServerName":"My Library"}'):
        self.body = io.BytesIO(data)
    def __enter__(self):
        return self
    def __exit__(self, *unused):
        return False
    def read(self, count):
        return self.body.read(count)


def healthy(request, timeout):
    assert request.full_url == "http://127.0.0.1:8096/System/Info/Public"
    assert timeout == 3
    return Reply()


def offline(request, timeout):
    raise OSError("local Jellyfin not running")


class HostMediaAdoptionTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.path = self.root / "optiplex-now" / "media-public-endpoint.json"

    def test_review_is_read_only_and_does_not_leak_server_id(self):
        result = adoption.inspect(config_path=self.path, opener=healthy)
        self.assertEqual(result["status"], "local_jellyfin_found")
        self.assertTrue(result["can_approve"])
        self.assertFalse(result["changes_performed"])
        self.assertNotIn("our-jellyfin", str(result))
        self.assertFalse(self.path.exists())
        self.assertEqual(adoption.inspect(config_path=self.path, opener=offline)["status"],
                         "not_verified")
        self.assertFalse(self.path.parent.exists())

    def test_explicit_first_time_owner_approval_only_writes_one_private_file(self):
        if __import__("os").geteuid() == 0:
            self.skipTest("Owner GUI cannot write from a privileged/root user")
        self.assertEqual(adoption.approve_route(
            "https", 443, "/jellyfin",
            config_path=self.path, opener=healthy)["status"], "route_created")
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(json.loads(self.path.read_text()), {
            "version":1, "scheme":"https", "port":443, "base_path":"/jellyfin"})
        result = adoption.inspect(config_path=self.path, opener=healthy)
        self.assertEqual(result["status"], "already_configured")
        self.assertFalse(result["can_approve"])
        with self.assertRaises(ValueError):
            adoption.approve_route("http", 8096, "/",
                                 config_path=self.path, opener=healthy)
        self.assertEqual(json.loads(self.path.read_text())["scheme"], "https")

    def test_offline_refusal_invalid_routes_and_existing_file_preserved(self):
        if __import__("os").geteuid() == 0:
            self.skipTest("Owner GUI cannot write from a privileged/root user")
        for scheme, port, route in [
            ("ftp", 8096, "/"), ("http", True, "/"),
            ("http", 0, "/"), ("http", 65536, "/"),
            ("http", 8096, "//evil"), ("http", 8096, "/evil/path"),
            ("http", 8096, "/bad?key=1"),
        ]:
            with self.subTest(scheme=scheme, port=port, route=route):
                with self.assertRaises(ValueError):
                    adoption.approve_route(scheme, port, route,
                                           config_path=self.path, opener=healthy)
        with self.assertRaises(ValueError):
            adoption.approve_route("http", 8096, "/",
                                   config_path=self.path, opener=offline)
        self.assertFalse(self.path.exists())
        self.path.parent.mkdir()
        self.path.write_text("do not overwrite")
        self.path.chmod(0o600)
        self.assertEqual(adoption.inspect(
            config_path=self.path, opener=healthy)["status"], "unsafe_config")
        with self.assertRaises(ValueError):
            adoption.approve_route("http", 8096, "/",
                                   config_path=self.path, opener=healthy)
        self.assertEqual(self.path.read_text(), "do not overwrite")

    def test_reject_symlink_config_and_directory(self):
        if __import__("os").geteuid() == 0:
            self.skipTest("Owner GUI cannot write from a privileged/root user")
        destination = self.root / "unrelated.json"
        destination.write_text("preserve me")
        self.path.parent.mkdir()
        self.path.symlink_to(destination)
        self.assertEqual(adoption.inspect(
            config_path=self.path, opener=healthy)["status"], "unsafe_config")
        with self.assertRaises(ValueError):
            adoption.approve_route("http", 8096, "/",
                                   config_path=self.path, opener=healthy)
        self.assertEqual(destination.read_text(), "preserve me")
        self.path.unlink()
        self.path.parent.rmdir()
        self.path.parent.symlink_to(self.root)
        with self.assertRaises(ValueError):
            adoption.approve_route("http", 8096, "/",
                                   config_path=self.path, opener=healthy)
        self.assertFalse((self.root / "media-public-endpoint.json").exists())

    def test_package_and_gui_source_do_not_grant_docker_or_privileged_actions(self):
        gui = (ROOT / "src/host-media-setup.py").read_text()
        host = (ROOT / "src/host_setup.c").read_text()
        package = (ROOT / "package.py").read_text()
        self.assertIn("VIDEOS | USE EXISTING JELLYFIN", host)
        self.assertIn("host-media-setup.py", host)
        self.assertIn("host_media_adoption.py", package)
        self.assertIn("media_endpoint.py", package)
        self.assertIn("--approve-existing", gui)
        self.assertIn("--confirm-owner", gui)
        self.assertNotIn('"/usr/bin/docker"', gui)
        self.assertNotIn("pkexec", gui.lower())
        self.assertNotIn("chmod 777", gui.lower())
        for source in (gui, (ROOT / "server/host_media_adoption.py").read_text()):
            compile(source, "<host-media-setup>", "exec")


if __name__ == "__main__":
    unittest.main()
