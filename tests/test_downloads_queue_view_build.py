"""Compile and behavior-test the separate read-only GTK Downloads queue module."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]


class NativeDownloadsQueueTests(unittest.TestCase):
    def test_native_queue_widget_in_xvfb(self):
        flags=subprocess.check_output(
            ["pkg-config","--cflags","--libs","gtk+-3.0"],
            text=True).split()
        with tempfile.TemporaryDirectory() as tmp:
            exe=str(Path(tmp)/"queue-test")
            subprocess.run(["cc","-std=gnu11","-Wall","-Wextra",
                "-Werror=implicit-function-declaration",
                "-Werror=incompatible-pointer-types","-Isrc",
                "tests/test_downloads_queue_view.c",
                "src/downloads_queue_view.c","-o",exe,*flags,"-lm"],
                cwd=ROOT,check=True,capture_output=True)
            subprocess.run(["xvfb-run","-a",exe],cwd=ROOT,
                           check=True,capture_output=True,timeout=25)

    def test_queue_has_no_direct_docker_or_admin_transport(self):
        src=(ROOT/"src/downloads_queue_view.c").read_text()
        flow=(ROOT/"src/downloads_flow.c").read_text()
        self.assertNotIn("docker exec",src)
        self.assertNotIn("api/v2/",src)
        self.assertNotIn("ssh",src.lower())
        self.assertIn('"--native"',flow)
        self.assertIn('g_subprocess_communicate_utf8_async',flow)
        self.assertIn("owner_device_key_exists()",flow)
        self.assertNotIn("now_downloads_webview_new(target,job->host)",flow)


if __name__=="__main__":
    unittest.main()
