"""Polish release guards: browser Videos, distinct VPN health and shared theme."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SOURCE = (SRC / "main.c").read_text()
SHARED = (SRC / "now-theme.css").read_text()
PACKAGE = (ROOT / "package.py").read_text()


class AlphaPolishTests(unittest.TestCase):
    def test_browser_first_video_has_no_dead_embedded_action(self):
        self.assertIn('"OPEN VIDEO LIBRARY  ↗","videos-open-library"', SOURCE)
        self.assertIn('now_media_bind(videos_status_message,browser_open,NULL)', SOURCE)
        self.assertIn('GtkWidget*video_advanced=gtk_expander_new("VIDEO SETTINGS")', SOURCE)
        self.assertIn('if(index==1){now_media_open_videos();return;}', SOURCE)
        self.assertNotIn('"WATCH IN NOW"', SOURCE)
        self.assertNotIn('videos-open-in-app', SOURCE)
        self.assertNotIn('now_media_open_videos_in_app();', SOURCE)
        self.assertNotIn('now_tray_videos_open_in_app()', SOURCE)

    def test_vpn_dashboard_badge_is_not_a_kill_switch_claim(self):
        self.assertIn('metric_vpn=label("● DOWNLOAD VPN UNKNOWN","state")', SOURCE)
        self.assertIn('● DOWNLOAD VPN UNVERIFIED', SOURCE)
        self.assertIn('Gluetun container status from server diagnostics', SOURCE)
        self.assertIn('VPN  HEALTHY', SOURCE)
        self.assertIn('VPN  UNHEALTHY', SOURCE)
        self.assertNotIn('metric_vpn=label("VPN  --","statusmetric")', SOURCE)

    def test_shared_theme_is_packaged_for_native_windows(self):
        for name in ("now-theme.css", "now_theme.py"):
            self.assertIn("src/" + name, PACKAGE)
        for selector in ("window, dialog, popover", "button:disabled",
                         "checkbutton check:checked", "combobox button",
                         "textview text", "scrollbar slider", "entry:focus"):
            self.assertIn(selector, SHARED)
        self.assertIn('gtk_css_provider_load_from_path', SOURCE)
        self.assertIn('gtk_css_provider_load_from_path', (SRC / "host_setup.c").read_text())
        for path in ("owner-approvals-ui.py", "owner-enroll-ui.py",
                     "host-media-setup.py", "host-jellyfin-new-ui.py",
                     "owner-host-upgrade.py"):
            self.assertIn("install_theme()", (SRC / path).read_text(), path)


if __name__ == "__main__":
    unittest.main()
