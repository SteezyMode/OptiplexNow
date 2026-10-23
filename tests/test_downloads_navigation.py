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

    def test_embedded_webview_uses_full_downloads_page(self):
        self.assertNotIn('gtk_button_new_with_label("VUE TORRENT")', FLOW)
        self.assertNotIn('gtk_button_new_with_label("QUEUE SNAPSHOT")', FLOW)
        self.assertIn('gtk_widget_hide(status_label);', FLOW)
        self.assertIn('gtk_widget_set_no_show_all(status_label,TRUE);', FLOW)
        self.assertIn('gtk_stack_set_visible_child_name(GTK_STACK(queue_stack),"queue")', FLOW)
        self.assertIn('gtk_stack_set_visible_child_name(GTK_STACK(queue_stack),"web")', FLOW)

    def test_fresh_linux_profile_explains_missing_owner_enrollment(self):
        # Diagnostics must be specific and stop BEFORE any SSH/Docker request.
        first = FLOW.split("void now_downloads_refresh(", 1)[1].split(
            "static void show_web(", 1)[0]
        self.assertIn("owner_device_key_exists()", first)
        self.assertLess(first.index("owner_device_key_exists()"),
                        first.index("g_subprocess_newv("))
        self.assertIn("ordinary SSH authorization and Moonlight pairing do not enroll it", first)
        self.assertIn("OWNER DEVICE NOT ENROLLED", first)
        self.assertIn("DOWNLOADS NOT AVAILABLE", FLOW)
        self.assertNotIn('Queue unavailable. Check server connection.', FLOW)

    def test_wizard_does_not_pretend_ssh_approval_is_owner_enrollment(self):
        self.assertIn("This authorizes ordinary SSH only.", SHELL)
        self.assertIn("separate restricted device key", SHELL)
        self.assertIn("Automatic owner enrollment is not available in this build.", SHELL)
        self.assertIn("CONNECTION SETTINGS SAVED", SHELL)
        self.assertNotIn('add(six,label("READY","modalheading"),0);', SHELL)

    def test_does_not_repeat_owner_approval_or_leak_password(self):
        self.assertIn("if(same && webview && loaded_url", FLOW)
        self.assertNotIn("password=", FLOW.lower())
        self.assertNotIn("auth.cookie", FLOW.lower())

if __name__ == "__main__":
    unittest.main()
