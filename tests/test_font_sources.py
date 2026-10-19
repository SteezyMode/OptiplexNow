"""The two bundled Google Fonts files must remain pinned and integrity-checked."""
import hashlib
from pathlib import Path
import runpy
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
VERIFY = runpy.run_path(str(ROOT / "tools/verify_font.py"))["verify"]


class FontIntegrityTests(unittest.TestCase):
    def test_verifier_accepts_exact_bytes_only(self):
        data = b"test-only-font-fixture"
        blob = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / "fixture.ttf"
            file.write_bytes(data)
            self.assertTrue(VERIFY(file, blob, len(data)))
            self.assertFalse(VERIFY(file, blob, len(data) + 1))
            file.write_bytes(data + b"!")
            self.assertFalse(VERIFY(file, blob, len(data) + 1))
            with self.assertRaises(ValueError):
                VERIFY(file, "not-a-sha", len(data))

    def test_font_sources_are_immutable_and_downloads_atomic(self):
        make = (ROOT / "Makefile").read_text()
        self.assertIn("FONT_REV = 47d54ca1ebb14fd864695f1d39dc734f39017c33", make)
        self.assertNotIn("google/fonts/main/ofl", make)
        self.assertIn("INTER_BLOB = 047c92f6e2212473dc436020afed689527076d44", make)
        self.assertIn("LIMELIGHT_BLOB = 879e7f9d7a6240defbc5ecf97cd819905ef0c242", make)
        self.assertEqual(make.count("python3 tools/verify_font.py"), 2)
        self.assertEqual(make.count('trap \'rm -f "$$tmp"\' EXIT'), 2)


if __name__ == "__main__":
    unittest.main()
