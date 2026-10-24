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

    def test_dashboard_is_explicitly_selected_after_pages_become_visible(self):
        # Downloads is shown during stack creation. If Dashboard is only the
        # implicit default, GTK may leave Downloads as the visible child.
        startup = SHELL.split(" reflow(initial_width);", 1)[1].split(
            " /* Initialize the tray", 1)[0]
        self.assertIn("gtk_widget_show_all(downloads_page);", SHELL)
        self.assertIn("gtk_widget_show_all(dash_scroll);", startup)
        self.assertIn("gtk_widget_show_all(software_scroll);", startup)
        self.assertIn('now_nav_show_page(main_pages,first_run?"dashboard":now_ui_state_start_page());', startup)
        self.assertLess(startup.index("gtk_widget_show_all(dash_scroll);"),
                        startup.index('now_nav_show_page(main_pages,'))
        self.assertNotIn('if(strcmp(start,"dashboard")!=0)', startup)

    def test_beta_defers_downloads_startup_without_disabling_navigation(self):
        # Earlier beta settings may contain start_page=downloads. The
        # state loader normalizes that to Dashboard and Settings does not
        # advertise an unsupported Downloads startup option.
        STATE = (ROOT / "src/ui_state.c").read_text(encoding="utf-8")
        self.assertIn('start_page="dashboard"', STATE)
        self.assertIn('!strcmp(page,"software")', STATE)
        self.assertNotIn('!strcmp(page,"downloads")', STATE)
        self.assertNotIn('gtk_combo_box_text_append(GTK_COMBO_BOX_TEXT(startup_choice),"downloads","Downloads");', SHELL)
        self.assertNotIn("startup_downloads_mapped", SHELL)
        self.assertIn('now_downloads_open(cfg[0],cfg[1],cfg[7]);', SHELL)
        self.assertIn('g_signal_connect(downloads_tab,"clicked",G_CALLBACK(on_downloads_tab),NULL);', SHELL)

    def test_embedded_webview_uses_full_downloads_page(self):
        self.assertNotIn('gtk_button_new_with_label("VUE TORRENT")', FLOW)
        self.assertNotIn('gtk_button_new_with_label("QUEUE SNAPSHOT")', FLOW)
        self.assertIn('gtk_widget_hide(status_label);', FLOW)
        self.assertIn('gtk_widget_set_no_show_all(status_label,TRUE);', FLOW)
        self.assertIn('gtk_stack_set_visible_child_name(GTK_STACK(queue_stack),"queue")', FLOW)
        self.assertIn('gtk_stack_set_visible_child_name(GTK_STACK(queue_stack),"web")', FLOW)

    def test_one_bounded_readonly_retry_after_transient_first_open_failure(self):
        self.assertIn("static gboolean reconnect_once(gpointer unused)", FLOW)
        self.assertIn("g_timeout_add_seconds(4,reconnect_once,NULL)", FLOW)
        self.assertIn("!reconnect_used && !reconnect_source", FLOW)
        self.assertIn("reconnect_used=TRUE;", FLOW)
        self.assertIn("if(reconnect_source){g_source_remove(reconnect_source);reconnect_source=0;}", FLOW)
        self.assertIn("gtk_widget_get_mapped(queue_stack)", FLOW)
        # Recovery must reuse the fixed read-only queue helper, not start a
        # Steam or download mutation or circumvent owner authorization.
        cb = FLOW.split("static gboolean reconnect_once(", 1)[1].split(
            "/* Local credential presence", 1)[0]
        self.assertIn("now_downloads_open(last_host,last_user,last_override);", cb)
        self.assertNotIn("ssh-copy-id", FLOW)
        self.assertNotIn("games_start", cb)

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
        self.assertIn("Moonlight pairing alone is not owner-service approval.", SHELL)
        self.assertIn("separate restricted device key", SHELL)
        self.assertIn("Use REQUEST OWNER DEVICE APPROVAL on the Games page", SHELL)
        self.assertIn("CONNECTION SETTINGS SAVED", SHELL)
        self.assertIn("GAMES ACCESS UNVERIFIED. CHECK OWNER DEVICE APPROVAL OR HOST STATUS", SHELL)
        self.assertNotIn('add(six,label("READY","modalheading"),0);', SHELL)

    def test_normal_wizard_never_offers_unrestricted_admin_ssh(self):
        wizard = SHELL.split("static void on_wizard(void*w,void*p)", 1)[1].split(
            "static gboolean first_setup", 1)[0]
        self.assertNotIn('"w_pair"', wizard)
        self.assertNotIn('"w_relay"', wizard)
        self.assertNotIn('"AUTHORIZE SSH KEY"', wizard)
        self.assertNotIn('"AUTHORIZE RELAY KEY"', wizard)
        self.assertNotIn('"SECURE ACCESS"', wizard)
        self.assertIn("AUTHORIZE OWNER ADMIN SSH KEY", SHELL)
        self.assertIn("AUTHORIZE WAKE RELAY SSH KEY", SHELL)
        self.assertIn("gtk_grid_attach(GTK_GRID(advanced_grid),admin_ssh,0,8,2,1);", SHELL)
        self.assertIn("c->staged[2],c->staged[3],c->staged[4]", SHELL)
        self.assertIn("ADVANCED OWNER ADMINISTRATION ONLY.", SHELL)

    def test_does_not_repeat_owner_approval_or_leak_password(self):
        self.assertIn("if(same && webview && loaded_url", FLOW)
        self.assertNotIn("password=", FLOW.lower())
        self.assertNotIn("auth.cookie", FLOW.lower())

if __name__ == "__main__":
    unittest.main()
