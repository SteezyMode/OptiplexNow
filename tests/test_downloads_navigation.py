"""Regression contract: Downloads page and tray must not rebuild WebKit per visit.

Physical GTK/WebKit session continuity still needs a MacBook acceptance pass.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
FLOW = (ROOT / "src/downloads_flow.c").read_text(encoding="utf-8")
TRAY = (ROOT / "src/tray_actions.c").read_text(encoding="utf-8")
SHELL = (ROOT / "src/main.c").read_text(encoding="utf-8")

class DownloadsNavigationContract(unittest.TestCase):
    def test_view_reused_when_owner_and_override_unchanged(self):
        opening = FLOW.split("void now_downloads_open(", 1)[1].split(
            "GtkWidget *now_downloads_page(", 1)[0]
        self.assertIn("g_strcmp0(last_host,host)==0", opening)
        self.assertIn("g_strcmp0(last_user,user)==0", opening)
        self.assertIn("g_strcmp0(last_override,webui_url)==0", opening)
        self.assertIn("if(same && webview && loaded_url", opening)
        self.assertIn("show_web(NULL,NULL);", opening)
        self.assertIn("if(!same){", opening)
        self.assertIn("gtk_container_remove(GTK_CONTAINER(view_holder),webview);", opening)
        self.assertIn("if(same && running)return;", opening)
        self.assertIn("now_downloads_refresh(host,user);", opening)

    def test_tray_navigates_to_app_downloads_page(self):
        self.assertIn("} else if (action == 4) {", TRAY)
        self.assertIn("handlers->show_window(context);", TRAY)
        self.assertIn("handlers->launch_service(context, action);", TRAY)
        self.assertIn("else if(n==4)launch_torrents();", SHELL)
        self.assertIn("static void launch_torrents(void){open_downloads_page();}", SHELL)
        self.assertIn('now_nav_show_page(main_pages,"downloads");', SHELL)

    def test_does_not_repeat_owner_approval_or_leak_password(self):
        self.assertIn("if(same && webview && loaded_url", FLOW)
        self.assertNotIn("password=", FLOW.lower())
        self.assertNotIn("auth.cookie", FLOW.lower())

if __name__ == "__main__":
    unittest.main()
