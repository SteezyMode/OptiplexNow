"""Native Wolf/Moonlight pairing regression checks.

The actual new-device cryptographic pairing needs a physical Linux client and
an owner-controlled Wolf host; source contracts do not certify this.
"""
from pathlib import Path
import unittest

SRC = (Path(__file__).resolve().parents[1] / "src" / "main.c").read_text()

class NativePairingTests(unittest.TestCase):
    def test_client_does_not_launch_moonlight_pair_in_terminal(self):
        start=SRC.index("static void pair_wolf(void){")
        end=SRC.index("static void on_games_action(",start)
        section=SRC[start:end]
        self.assertNotIn("terminal_launch(",section)
        self.assertNotIn('"sudo"',section)
        self.assertIn('g_subprocess_new(',section)
        self.assertIn('"pair",cfg[0]',section)
        self.assertIn('find_native_moonlight(',section)
        self.assertIn('"flatpak","run","com.moonlight_stream.Moonlight","pair",cfg[0]',section)
        self.assertIn('appimage,"pair",cfg[0]',section)
        self.assertIn("if(!now_valid_host(cfg[0]))",section)
        self.assertNotIn("now_valid_user",section)
        self.assertIn("g_object_unref(process);",section)

    def test_owner_pin_needs_approval_not_remote_admin(self):
        self.assertIn("server owner must open Wolf's one-time pairing link",SRC)
        self.assertIn("START MOONLIGHT PAIRING",SRC)
        self.assertIn("SSH is NOT required to stream games",SRC)
        self.assertNotIn('"/api/v1/pair/client"',SRC)
        self.assertNotIn('"/var/run/docker.sock"',SRC)

    def test_existing_stream_shortcut_stays_wolf_native(self):
        self.assertIn('launch_wolf_app("Steam")',SRC)
        self.assertIn('launch_wolf_app("OptiPlex Studio Desktop")',SRC)

if __name__=="__main__":
    unittest.main()
