"""Client-first onboarding contract; no SSH forced for streaming or terminals for Moonlight.

CI's native GTK build and installed-package smoke tests remain required.
"""
import unittest
from pathlib import Path

MAIN=(Path(__file__).resolve().parents[1]/"src"/"main.c").read_text(encoding="utf-8")

class ClientFirstRunTests(unittest.TestCase):
    def test_basic_streaming_requires_host_not_ssh_user(self):
        start=MAIN.index("static void wizard_validate(")
        end=MAIN.index("static void wizard_save(",start)
        validate=MAIN[start:end]
        self.assertIn("int ok=now_valid_host(",validate)
        self.assertIn("if(*optional_user && !now_valid_user(optional_user))ok=0;",validate)
        self.assertIn("SSH USER (OPTIONAL",MAIN)
        self.assertIn("Skip this page for Steam and Wolf streaming",MAIN)

    def test_saved_stream_does_not_force_ssh_identity(self):
        start=MAIN.index("static void wizard_save(")
        end=MAIN.index("static void wizard_service_check(",start)
        saved=MAIN[start:end]
        self.assertIn("(*values[1]&&!now_valid_user(values[1]))",saved)
        self.assertIn("config_save();",saved)

    def test_moonlight_installs_after_confirmation_without_terminal(self):
        start=MAIN.index("static void install_moonlight(void){")
        end=MAIN.index("static void pair_wolf(void)",start)
        installer=MAIN[start:end]
        self.assertIn("gtk_dialog_run(GTK_DIALOG(dialog))",installer)
        self.assertIn("if(response!=GTK_RESPONSE_OK)return;",installer)
        self.assertIn('"flatpak","remote-add","--user"',installer)
        self.assertIn('"flatpak","install","--user","--noninteractive","--assumeyes"',MAIN)
        self.assertIn("g_subprocess_wait_check_async(",installer)
        self.assertNotIn("terminal_launch(",installer)
        self.assertNotIn('"sh","-c"',installer)
        self.assertIn("moonlight_install_running",installer)

    def test_existing_moonlight_is_preserved(self):
        self.assertIn("if(has_moonlight()){moonlight_install_status",MAIN)
        self.assertIn('now_resolve_executable("moonlight","/snap/bin/moonlight"',MAIN)
        self.assertIn("wizard_moonlight_label=NULL",MAIN)

if __name__=="__main__":
    unittest.main()
