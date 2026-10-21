"""Graphical Tailscale installer tests. Never uses privileges or the network."""
import contextlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest import mock

MODULE = Path(__file__).resolve().parents[1] / "src" / "tailscale-install.py"
spec = importlib.util.spec_from_file_location("tailscale_install", MODULE)
install = importlib.util.module_from_spec(spec)
spec.loader.exec_module(install)


class TailscaleInstallerTests(unittest.TestCase):
    def test_supported_debian_and_ubuntu_derivatives(self):
        cases = [
            ({"ID": "ubuntu", "VERSION_CODENAME": "noble"}, ("ubuntu", "noble")),
            ({"ID": "pop", "VERSION_CODENAME": "jammy",
              "UBUNTU_CODENAME": "jammy"}, ("ubuntu", "jammy")),
            ({"ID": "linuxmint", "VERSION_CODENAME": "wilma",
              "UBUNTU_CODENAME": "noble"}, ("ubuntu", "noble")),
            ({"ID": "debian", "VERSION_CODENAME": "trixie"}, ("debian", "trixie")),
        ]
        for release, expected in cases:
            with self.subTest(release=release):
                self.assertEqual(install.distro(release), expected)

    def test_unknown_and_unvalidated_os_fails_closed(self):
        for release in (
            {"ID": "arch", "VERSION_CODENAME": "rolling"},
            {"ID": "linuxmint", "VERSION_CODENAME": "wilma"},
            {"ID": "ubuntu", "VERSION_CODENAME": "mantic"},
            {"ID": "debian", "VERSION_CODENAME": "sid"},
        ):
            with self.subTest(release=release):
                with self.assertRaises(ValueError):
                    install.distro(release)

    def test_installer_only_uses_upstream_signed_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            key_path = Path(tmp) / "tailscale.gpg"
            repo_path = Path(tmp) / "tailscale.list"
            upstream = ("deb [signed-by=" + str(key_path) +
                        "] https://pkgs.tailscale.com/stable/ubuntu noble main")
            def fixture(_base, _codename, suffix):
                return b"f" * 512 if suffix == "noarmor.gpg" else (
                    "# official\n" + upstream + "\n").encode()
            with mock.patch.object(install, "KEYRING", key_path), \
                 mock.patch.object(install, "REPOSITORY", repo_path), \
                 mock.patch.object(install, "upstream_data", side_effect=fixture):
                install.install_repository("ubuntu", "noble")
                self.assertEqual(repo_path.read_text().strip(), upstream)
                self.assertEqual(key_path.read_bytes(), b"f" * 512)
                self.assertEqual(repo_path.stat().st_mode & 0o777, 0o644)

    def test_existing_custom_apt_source_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            key_path = Path(tmp) / "tailscale.gpg"
            repo_path = Path(tmp) / "tailscale.list"
            repo_path.write_text("custom source, leave alone\n")
            with mock.patch.object(install, "KEYRING", key_path), \
                 mock.patch.object(install, "REPOSITORY", repo_path), \
                 mock.patch.object(install, "upstream_data", side_effect=[
                     b"x" * 256, b"deb [signed-by=/wrong] https://bad.invalid stable main"
                 ]):
                with self.assertRaises(ValueError):
                    install.install_repository("ubuntu", "noble")
            self.assertEqual(repo_path.read_text(), "custom source, leave alone\n")

    def test_existing_tailscale_is_left_untouched(self):
        with mock.patch.object(install.os, "geteuid", return_value=0), \
             mock.patch.object(install.shutil, "which", return_value="/usr/bin/tailscale"), \
             mock.patch.object(install, "run") as run:
            with contextlib.redirect_stdout(io.StringIO()) as output:
                install.main()
            self.assertEqual(output.getvalue().strip(), "ALREADY_INSTALLED")
            run.assert_not_called()

    def test_explicit_authorization_required(self):
        with mock.patch.object(install.os, "geteuid", return_value=1000), \
             mock.patch.object(install, "run") as run:
            with self.assertRaises(PermissionError):
                install.main()
            run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
