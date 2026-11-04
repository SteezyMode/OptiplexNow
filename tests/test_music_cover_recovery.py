"""Persistent DroppedNeedle synthetic-ID artwork recovery regression checks.

Runs without DroppedNeedle/Spotify/accounts/network access and never touches
user library files. Exercises exact matching, multiple candidates, cached
results, local art precedence, failure, and host patch/version guards.
"""
from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock

ROOT=Path(__file__).resolve().parents[1]
def load(name,relative):
    spec=importlib.util.spec_from_file_location(name,ROOT/relative)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

art=load("bruiser_cover_recovery","deploy/music/bruiser_cover_recovery.py")
installer=load("bruiser_art_installer","deploy/music/install_album_art_recovery.py")
SYN="9397b6da-1fb4-5107-8261-ddcceb404c50"  # real reported local UUIDv5
REAL="e7f4dc05-1234-4a04-a22b-829581e1f043"
OTHER="c91caa11-2345-4567-8123-234567890abc"
PNG=b"\x89PNG\r\n\x1a\n"+b"test-raster-bytes"

def album(title,artist,year):
    return SimpleNamespace(title=title,artist_name=artist,year=year)
def match(mbid,title,artist,year):
    return SimpleNamespace(musicbrainz_id=mbid,title=title,artist=artist,year=year)

class Disk:
    def __init__(self):
        self.data={}
        self.misses={}
        self.writes=[]
    def get_file_path(self,ident,size):
        return str(ident)+"_"+str(size)
    async def read(self,path,keys):
        return self.data.get(path)
    async def write(self,path,data,mime,meta=None,is_monitored=False):
        self.data[path]=(data,mime,meta or {})
        self.writes.append((path,is_monitored,meta))
    async def is_negative(self,path):
        return path in self.misses
    async def write_negative(self,path,ttl_seconds=0):
        self.misses[path]=ttl_seconds

def setup(candidates,image=(PNG,"image/png","caa"),local=None,disk=None):
    disk=disk or Disk()
    cover=SimpleNamespace(
        disk_cache=disk,
        _local_album_cover=AsyncMock(return_value=local),
        get_release_group_cover=AsyncMock(return_value=image),
    )
    repo=SimpleNamespace(search_release_groups=AsyncMock(return_value=candidates))
    svc=SimpleNamespace(coverart=cover)
    return svc,repo,disk

class CoverIdTests(unittest.TestCase):
    def test_synthetic_is_not_a_genuine_mbid(self):
        self.assertTrue(art.is_local_album_id(SYN))
        self.assertFalse(art.is_local_album_id(REAL))
        self.assertFalse(art.is_local_album_id("bad"))
        self.assertFalse(art.is_local_album_id(None))

    def test_blue_sky_noise_has_precise_match(self):
        alb=album("Blue Sky Noise","Circa Survive",2010)
        candidates=[match(REAL,"Blue Sky Noise","Circa Survive",2010),
                    match(OTHER,"Blue Sky Noise","Different Artist",2010)]
        self.assertEqual(art.verified_release_group(alb,candidates),REAL)

    def test_kid_cudi_original_full_title_is_not_guessing(self):
        alb=album("Man on the Moon: The End of Day","Kid Cudi",2009)
        candidates=[match(REAL,"Man on the Moon: The End of Day","Kid Cudi",2009),
                    match(OTHER,"Man on the Moon II: The Legend of Mr. Rager",
                          "Kid Cudi",2010)]
        self.assertEqual(art.verified_release_group(alb,candidates),REAL)

    def test_wrong_year_or_ambiguous_release_does_not_autofill(self):
        alb=album("Blue Sky Noise","Circa Survive",2010)
        self.assertIsNone(art.verified_release_group(alb,[
            match(REAL,"Blue Sky Noise","Circa Survive",2011)]))
        self.assertIsNone(art.verified_release_group(alb,[
            match(REAL,"Blue Sky Noise","Circa Survive",2010),
            match(OTHER,"Blue Sky Noise","Circa Survive",2010)]))

    def test_synthetic_uuid_as_candidate_is_not_accepted(self):
        self.assertIsNone(art.verified_release_group(
            album("Blue Sky Noise","Circa Survive",2010),
            [match(SYN,"Blue Sky Noise","Circa Survive",2010)]))
    def test_no_svg_spoofing(self):
        self.assertFalse(art.valid_image((b"<svg/>","image/png","remote")))
        self.assertFalse(art.valid_image((PNG,"image/svg+xml","remote")))

class CoverResolverTests(unittest.IsolatedAsyncioTestCase):
    async def test_remote_exact_match_writes_monitored_local_id_cache(self):
        svc,repo,disk=setup(
            [match(REAL,"Blue Sky Noise","Circa Survive",2010)])
        original=album("Blue Sky Noise","Circa Survive",2010)
        result=await art.recover_album_cover(
            svc,original,SYN,"220",mb_repository=repo,priority="background")
        self.assertEqual(result[:2],(PNG,"image/png"))
        self.assertEqual(disk.writes[0][0],"rg_"+SYN+"_220")
        self.assertTrue(disk.writes[0][1])
        self.assertEqual(disk.writes[0][2]["matched_mbid"],REAL)
        second=await art.recover_album_cover(
            svc,original,SYN,"220",mb_repository=repo,priority="background")
        self.assertEqual(second[0],PNG)
        self.assertEqual(repo.search_release_groups.await_count,1)
        svc.coverart.get_release_group_cover.assert_awaited_once()

    async def test_local_folder_or_embedded_art_beats_remote(self):
        svc,repo,disk=setup(
            [match(REAL,"Man on the Moon: The End of Day","Kid Cudi",2009)],
            local=(PNG,"image/png","embedded"))
        result=await art.recover_album_cover(
            svc,album("Man on the Moon: The End of Day","Kid Cudi",2009),
            SYN,"220",mb_repository=repo,priority="background")
        self.assertEqual(result[2],"embedded")
        repo.search_release_groups.assert_not_called()

    async def test_ambiguous_match_never_caches_wrong_art(self):
        svc,repo,disk=setup([
            match(REAL,"Blue Sky Noise","Circa Survive",2010),
            match(OTHER,"Blue Sky Noise","Circa Survive",2010)])
        result=await art.recover_album_cover(
            svc,album("Blue Sky Noise","Circa Survive",2010),SYN,"220",
            mb_repository=repo,priority="background")
        self.assertIsNone(result)
        self.assertEqual(disk.data,{})
        self.assertEqual(disk.misses["rg_"+SYN+"_220"],6*3600)
        svc.coverart.get_release_group_cover.assert_not_called()

    async def test_provider_outage_fails_closed_and_retries(self):
        svc,repo,disk=setup([])
        repo.search_release_groups=AsyncMock(side_effect=RuntimeError("offline"))
        result=await art.recover_album_cover(
            svc,album("Blue Sky Noise","Circa Survive",2010),SYN,"220",
            mb_repository=repo,priority="background")
        self.assertIsNone(result)
        self.assertEqual(disk.misses["rg_"+SYN+"_220"],5*60)
        svc.coverart.get_release_group_cover.assert_not_called()

class InstallerTests(unittest.TestCase):
    def test_route_patch_preserves_track_artist_and_auth(self):
        source='from api.compat.subsonic.auth import resolve_subsonic_user\n' + (
            installer.EXPECTED
        )
        patched=installer.patch_router(source)
        self.assertIn("is_local_album_id(internal)",patched)
        self.assertIn("await recover_album_cover(",patched)
        self.assertIn("private, no-store",patched)
        self.assertIn('    elif kind == "track":',patched)
        self.assertIn("resolve_subsonic_user",patched)
        self.assertNotIn(installer.EXPECTED,patched)
        with self.assertRaises(installer.InstallError):
            installer.patch_router(patched)
    def test_unrecognized_upstream_version_fails_before_deployment(self):
        with self.assertRaises(installer.InstallError):
            installer.patch_router("changed implementation")

if __name__=="__main__":
    unittest.main()
