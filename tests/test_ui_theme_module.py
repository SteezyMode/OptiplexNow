"""The desktop stylesheet is compiled into the binary, not loaded from disk.

Style assertions live in the theme module; application behavior and launch
contracts remain in main.c. This test does not query a host or user's data.
"""
import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "src/main.c").read_text(encoding="utf-8")
THEME = (ROOT / "src/ui_theme.c").read_text(encoding="utf-8")
HEADER = (ROOT / "src/ui_theme.h").read_text(encoding="utf-8")
MAKE = (ROOT / "Makefile").read_text(encoding="utf-8")


class BuiltinThemeTests(unittest.TestCase):
    def test_main_delegates_to_one_compiled_theme_module(self):
        self.assertIn('#include "ui_theme.h"', MAIN)
        self.assertIn("gtk_css_provider_load_from_data(GTK_CSS_PROVIDER(cp),now_ui_theme_css(),-1,NULL)", MAIN)
        self.assertNotIn("static const char *CSS =", MAIN)
        self.assertNotIn('g_file_get_contents("ui_theme', MAIN)
        self.assertIn("const char *now_ui_theme_css(void);", HEADER)
        self.assertIn("src/ui_theme.c src/ui_games.c", MAKE)
        self.assertIn("src/ui_theme.c src/ui_theme.h", MAKE)

    def test_theme_is_exactly_one_valid_concatenated_c_literal(self):
        prefix = "    static const char css[] ="
        self.assertEqual(THEME.count(prefix), 1)
        self.assertEqual(THEME.count("    return css;"), 1)
        fragment = THEME.split(prefix, 1)[1].split("    return css;", 1)[0]
        lines = [line.strip().rstrip(";") for line in fragment.splitlines()
                 if line.strip().startswith('"')]
        self.assertGreater(len(lines), 150)
        css = "".join(ast.literal_eval(line) for line in lines)
        for selector in (
            "* {font-family:'Inter',sans-serif;}",
            "#music-home {",
            "button.now-action {",
            "#tile {",
            "#settingscard {",
            "assistant button:hover {",
        ):
            self.assertIn(selector, css)
        self.assertNotIn("\\0", css)
        self.assertFalse(css.startswith("\\n"))

    def test_style_owned_by_one_module_not_a_runtime_config_file(self):
        self.assertEqual(MAIN.count("now_ui_theme_css()"), 1)
        self.assertNotIn("src/ui_theme.c", MAIN)
        self.assertNotIn("fopen(", THEME)
        self.assertNotIn("g_file_get_contents(", THEME)


if __name__ == "__main__":
    unittest.main()
