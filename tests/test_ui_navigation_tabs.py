"""Exercise real GTK3 top-level tab selection under a virtual display."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class NavigationTabsTest(unittest.TestCase):
    def test_active_top_level_tab(self):
        required = ("cc", "pkg-config", "xvfb-run")
        if any(not shutil.which(binary) for binary in required):
            self.skipTest("GTK3 C compiler or Xvfb unavailable")
        flags = subprocess.run(
            ["pkg-config", "--cflags", "--libs", "gtk+-3.0"],
            capture_output=True, text=True)
        if flags.returncode:
            self.skipTest("GTK3 development files unavailable")
        with tempfile.TemporaryDirectory() as directory:
            executable = str(Path(directory) / "navigation-test")
            command = [
                "cc", "-std=c11", "-Wall", "-Wextra", "-Werror",
                "-Isrc", "tests/test_ui_navigation_tabs.c",
                "src/ui_navigation.c", "-o", executable,
            ] + flags.stdout.split()
            subprocess.run(command, cwd=ROOT, check=True, timeout=30)
            subprocess.run(["xvfb-run", "-a", executable], cwd=ROOT,
                           check=True, timeout=30)


if __name__ == "__main__":
    unittest.main()
