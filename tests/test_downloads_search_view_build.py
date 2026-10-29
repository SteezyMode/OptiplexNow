"""Compile native Downloads search independently and exercise GTK parser in Xvfb."""
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]

class NativeSearchViewTests(unittest.TestCase):
    def test_native_search_view_in_xvfb(self):
        flags=subprocess.check_output(
            ["pkg-config","--cflags","--libs","gtk+-3.0","gio-2.0"],
            text=True).split()
        with tempfile.TemporaryDirectory() as temp:
            exe=str(Path(temp)/"search-view-test")
            subprocess.run(["cc","-std=gnu11","-Wall","-Wextra",
                 "-Werror=incompatible-pointer-types",
                 "-Werror=implicit-function-declaration","-Isrc",
                 "tests/test_downloads_search_view.c",
                 "src/downloads_search_view.c","-o",exe,*flags],
                 cwd=ROOT,check=True,capture_output=True)
            result=subprocess.run(["xvfb-run","-a",exe],cwd=ROOT,
                      capture_output=True,text=True,timeout=25,check=False)
            self.assertEqual(result.returncode,0,
                             result.stdout+"\n"+result.stderr)
    def test_search_stays_in_downloads_page_and_queue_remains_visible(self):
        flow=(ROOT/"src/downloads_flow.c").read_text()
        module=(ROOT/"src/downloads_search_view.c").read_text()
        self.assertIn("now_downloads_search_view_new()",flow)
        self.assertIn("now_downloads_queue_view_new()",flow)
        self.assertIn("gtk_stack_add_named(GTK_STACK(downloads_subtabs),search,\"search\")",flow)
        self.assertIn("gtk_stack_add_named(GTK_STACK(downloads_subtabs),transfers,\"transfers\")",flow)
        self.assertIn("gtk_box_pack_start(GTK_BOX(search),search_view,TRUE,TRUE,0)",flow)
        self.assertIn("gtk_box_pack_start(GTK_BOX(view),s->results,TRUE,TRUE,0)",module)
        self.assertIn("gtk_widget_set_vexpand(s->results,TRUE)",module)
        self.assertIn("gtk_box_pack_start(GTK_BOX(transfers),queue_view",flow)
        self.assertIn('"/usr/bin/python3",s->helper,s->host,s->user,query,NULL',module)
        self.assertIn('g_subprocess_communicate_utf8_async',module)
        self.assertNotIn("torrents/add",module)
        self.assertNotIn("docker exec",module)

if __name__=="__main__":
    unittest.main()
