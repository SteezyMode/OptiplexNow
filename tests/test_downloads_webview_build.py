"""Runtime-optional WebKitGTK gate: compile the security policy under GTK3."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
class DownloadsWebviewTests(unittest.TestCase):
    def test_webview_policy_native(self):
        flags=subprocess.check_output(
            ["pkg-config","--cflags","--libs","gtk+-3.0","gio-2.0"],
            text=True).split()
        with tempfile.TemporaryDirectory() as temp:
            exe=str(Path(temp)/"test-webui")
            subprocess.run(["cc","-std=gnu11","-Wall","-Wextra",
                            "-Werror=incompatible-pointer-types",
                            "-Werror=implicit-function-declaration",
                            "-Isrc","tests/test_downloads_webview.c",
                            "src/downloads_webview.c","-o",exe,
                            *flags,"-ldl"],cwd=ROOT,
                           stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True)
            subprocess.run([exe],cwd=ROOT,stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE,check=True)

    def test_owner_gate_remains_outside_webview(self):
        flow=(ROOT/"src/downloads_flow.c").read_text()
        shell=(ROOT/"src/main.c").read_text()
        web=(ROOT/"src/downloads_webview.c").read_text()
        self.assertIn("now_downloads_webview_url_allowed", flow)
        self.assertIn("g_subprocess_get_successful(job->proc)",flow)
        self.assertIn("now_downloads_webview_new(pending_web_url,pending_web_host)",flow)
        self.assertIn("now_downloads_open(cfg[0],cfg[1],cfg[7]);",shell)
        self.assertIn("webkit_policy_decision_ignore",web)
        self.assertIn("webkit_download_cancel",web)
        self.assertNotIn("docker exec",flow)
        self.assertNotIn("docker exec",web)

if __name__=="__main__":
    unittest.main()
