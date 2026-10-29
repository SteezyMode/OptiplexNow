"""End-to-end source contracts for progress after qBittorrent's first batch."""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
HOST=(ROOT/"server/download_search.py").read_text()
CLIENT=(ROOT/"src/download-search-client.py").read_text()
VIEW=(ROOT/"src/downloads_search_view.c").read_text()
MAIN=(ROOT/"src/main.c").read_text()

class StreamingPolishTests(unittest.TestCase):
    def test_slow_plugin_bounded_window_is_supported_through_transport(self):
        self.assertIn("for _ in range(120):", HOST)
        self.assertIn("deadline=time.monotonic()+150", HOST)
        self.assertIn("count>=128", CLIENT)
        self.assertIn("offset\":received", HOST)
        self.assertIn('frame={**last,"partial"', HOST)
        self.assertIn('if(append && !s->received_initial)', VIEW)
        self.assertIn('if(ok && count+(append?s->result_count:0)>1000)', VIEW)

    def test_no_endless_searching_after_client_process_completes(self):
        self.assertIn('}else if(s->partial){', VIEW)
        self.assertIn('search time limit reached', VIEW)
        self.assertIn('of %"G_GINT64_FORMAT" results', VIEW)
        self.assertIn("s->running=FALSE;", VIEW)

    def test_dashboard_vpn_matches_download_page_wording(self):
        for text in ("VPN: HEALTHY", "VPN: UNVERIFIED", "VPN: UNKNOWN"):
            self.assertIn(text, MAIN)
        self.assertNotIn("DOWNLOAD VPN HEALTHY", MAIN)
        self.assertNotIn("DOWNLOAD VPN UNKNOWN", MAIN)

if __name__ == "__main__":
    unittest.main()
