"""Compile GTK inline destination independently, then run tests in Xvfb."""
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]

class DestinationViewTests(unittest.TestCase):
    def test_native_destination_widget_in_xvfb(self):
        flags=subprocess.check_output(
            ["pkg-config","--cflags","--libs","gtk+-3.0","gio-2.0"],
            text=True).split()
        with tempfile.TemporaryDirectory() as temp:
            exe=str(Path(temp)/"picker-test")
            subprocess.run(["cc","-std=gnu11","-Wall","-Wextra",
                 "-Werror=incompatible-pointer-types",
                 "-Werror=implicit-function-declaration","-Isrc",
                 "tests/test_downloads_destination_view.c",
                 "-o",exe,*flags],cwd=ROOT,check=True,capture_output=True)
            result=subprocess.run(["xvfb-run","-a",exe],cwd=ROOT,
                                  capture_output=True,text=True,
                                  timeout=25,check=False)
            self.assertEqual(result.returncode,0,
                             result.stdout+"\n"+result.stderr)
    def test_inline_picker_not_new_window(self):
        src=(ROOT/"src/downloads_destination_view.c").read_text()
        flow=(ROOT/"src/downloads_flow.c").read_text()
        self.assertIn("now_downloads_destination_view_new()",flow)
        self.assertIn("now_downloads_search_view_on_select(",flow)
        self.assertIn("now_downloads_destination_view_on_added(",flow)
        self.assertNotIn("gtk_window_new(",src)
        self.assertNotIn("docker exec",src)
        self.assertNotIn("torrents/add",src)
        self.assertIn("now_downloads_refresh(last_host,last_user)",flow)

if __name__=="__main__":
    unittest.main()
