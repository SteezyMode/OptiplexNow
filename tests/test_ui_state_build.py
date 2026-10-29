"""Compile/run isolated GLib UI persistence tests without opening GTK windows."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class UIStateTests(unittest.TestCase):
    def test_persistent_geometry_and_startup_page(self):
        flags = subprocess.check_output(
            ["pkg-config", "--cflags", "--libs", "glib-2.0"],
            text=True).split()
        with tempfile.TemporaryDirectory() as tmp:
            exe = str(Path(tmp) / "ui-state-test")
            subprocess.run(
                ["cc", "-std=c11", "-Wall", "-Wextra", "-Werror",
                 "-Isrc", "tests/test_ui_state.c", "src/ui_state.c",
                 "-o", exe, *flags],
                check=True, cwd=ROOT, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE)
            subprocess.run([exe], check=True, cwd=ROOT,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def test_gui_integration_remains_small_and_modular(self):
        main = (ROOT / "src" / "main.c").read_text()
        make = (ROOT / "Makefile").read_text()
        self.assertIn('#include "ui_state.h"', main)
        self.assertIn('#include "ui_navigation.h"', main)
        self.assertIn('now_nav_bind_link(dashboard_tab,main_pages,"dashboard");', main)
        self.assertIn('G_CALLBACK(now_nav_update_tabs),nav', main)
        self.assertIn('now_nav_show_page(main_pages,"downloads");', main)
        self.assertIn('now_ui_state_save();', main)
        self.assertNotIn('gtk_combo_box_text_append(GTK_COMBO_BOX_TEXT(startup_choice),"downloads","Downloads");', main)
        self.assertIn('now_ui_state_start_page()', main)
        self.assertIn('src/ui_state.c', make)
        self.assertIn('src/ui_navigation.c', make)


if __name__ == "__main__":
    unittest.main()
