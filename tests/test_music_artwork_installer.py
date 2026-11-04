"""Persistent artwork installer: fail-closed patch, no service/volume scope drift."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"deploy"/"music"/"install_artwork_fix.py"
spec=importlib.util.spec_from_file_location("bruiser_artwork_install",SOURCE)
installer=importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class ArtworkInstallerTests(unittest.TestCase):
    ROUTER='''async def _get_cover_art(c):
    if kind == "album":
        if await c.services.view.get_album(internal, user=c.user) is None:
            raise SubsonicError(70, "Album not found")
        result = await c.services.coverart.get_release_group_cover(
            internal, size, is_disconnected=disc
        )
'''

    def test_known_upstream_router_is_patched_once(self):
        updated=installer.patch_router(self.ROUTER)
        self.assertIn("album = await c.services.view.get_album(",updated)
        self.assertIn("from services.compat.bruiser_cover_resolver import missing_album_cover",updated)
        self.assertIn("result = await missing_album_cover(",updated)
        self.assertIn("if album is None:",updated)
        self.assertEqual(updated.count("if result is None:"),1)

    def test_installed_v1_router_is_upgradable_without_second_patch(self):
        once=installer.patch_router(self.ROUTER)
        twice=installer.patch_router(once)
        self.assertEqual(once,twice)
        self.assertEqual(twice.count(
            "from services.compat.bruiser_cover_resolver import missing_album_cover"),1)

    def test_installer_accepts_only_its_own_known_v1_for_upgrade(self):
        source=SOURCE.read_text()
        self.assertIn('fix_label != "bruiser-artwork-v1"',source)
        self.assertIn('old_image.endswith("-v1")',source)
        self.assertIn('old_image.endswith("-v2")',source)
        self.assertIn('VERSION = "bruiser-artwork-v2"',source)
        self.assertIn('bruiser/droppedneedle-artbase:',source)
        self.assertIn('if mounts(after) != original_mounts:',source)

    def test_unknown_router_never_patched(self):
        for source in ("",self.ROUTER+self.ROUTER,
                       self.ROUTER.replace("user=c.user","user=None")):
            with self.subTest(source=source[:40]),self.assertRaises(installer.InstallError):
                installer.patch_router(source)

    def test_patched_router_must_parse_as_python(self):
        with self.assertRaises(SyntaxError):
            installer.patch_router(self.ROUTER+"    not valid python ^^^\n")

    def test_image_preserves_existing_discover_fix(self):
        source=SOURCE.read_text()
        self.assertIn('old_image.startswith("bruiser/droppedneedle-discover:")',source)
        self.assertIn('optional_work_budget(OptionalWorkBudget(remaining=64))',source)
        self.assertIn('"--no-deps", "--force-recreate", CONTAINER)',source)
        self.assertIn('if mounts(after) != original_mounts:',source)
        self.assertIn('write_atomic(original,',source)
        self.assertIn('expected = {"/data","/app/config","/app/cache","/app/plugins","/app/imports"}',source)

if __name__=="__main__":
    unittest.main()
