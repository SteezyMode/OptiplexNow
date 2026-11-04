"""Offline contract checks for persistent synthetic-album artwork resolution."""
from __future__ import annotations

import asyncio
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import time
import types
import unittest
import uuid
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
P=ROOT/"deploy"/"music"/"bruiser_cover_resolver.py"
spec=importlib.util.spec_from_file_location("bruiser_cover_resolver",P)
resolver=importlib.util.module_from_spec(spec)
spec.loader.exec_module(resolver)

SYN=str(uuid.uuid5(uuid.NAMESPACE_URL,"Bruiser example: Blue Sky Noise"))
MB1="11111111-1111-4111-8111-111111111111"
MB2="22222222-2222-4222-8222-222222222222"

def release(mbid,title,artist,year):
    return {"musicbrainz_id":mbid,"title":title,"artist":artist,"year":year}


class CoverResolverPolicyTests(unittest.TestCase):
    def test_only_local_uuid_v5_is_eligible(self):
        self.assertTrue(resolver.synthetic_album_id(SYN))
        for value in (MB1,"", "not-a-uuid",None):
            self.assertFalse(resolver.synthetic_album_id(value))

    def test_blue_sky_noise_identified_conservatively(self):
        candidates=[
            release(MB2,"Blue Sky Noise","Some Other Artist",2010),
            release(MB1,"Blue Sky Noise","Circa Survive",2010),
        ]
        self.assertEqual(resolver.pick_verified_release_group(
            candidates,"Blue Sky Noise","Circa Survive",2010),MB1)

    def test_kid_cudi_correct_album_not_similar_album(self):
        self.assertEqual(resolver.pick_verified_release_group([
            release(MB2,"Man on the Moon II: The Legend of Mr. Rager","Kid Cudi",2010),
            release(MB1,"Man on the Moon: The End of Day","Kid Cudi",2009),
        ],"Man on the Moon: The End of Day","Kid Cudi",2009),MB1)

    def test_ambiguous_or_mismatched_matches_never_return_wrong_art(self):
        for candidates in (
            [release(MB1,"Blue Sky Noise","Circa Survive",2010),
             release(MB2,"Blue Sky Noise","Circa Survive",2010)],
            [release(MB1,"Blue Sky Noise","Different Artist",2010)],
            [release(MB1,"Blue Sky Noise","Circa Survive",2017)],
            [release(MB1,"Blue Sky Noise","Circa Survive",None)],
            [release(SYN,"Blue Sky Noise","Circa Survive",2010)],
            [],
        ):
            with self.subTest(candidates=candidates):
                self.assertIsNone(resolver.pick_verified_release_group(
                    candidates,"Blue Sky Noise","Circa Survive",2010))

    def test_persistent_mapping_is_keyed_by_local_identity_metadata(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(resolver,"CACHE_ROOT",Path(folder)):
                path=resolver._cache_path(SYN,"Blue Sky Noise","Circa Survive",2010)
                resolver._write_cache(path,MB1)
                self.assertEqual(resolver._read_cache(path),(True,MB1))
                self.assertEqual(path.parent,Path(folder))
                self.assertNotEqual(path,resolver._cache_path(
                    SYN,"Blue Sky Noise (Deluxe)","Circa Survive",2010))
                self.assertNotEqual(path,resolver._cache_path(
                    SYN,"Blue Sky Noise","Circa Survive",2011))
                self.assertFalse(resolver._read_cache(
                    resolver._cache_path(SYN,"Blue Sky Noise","Circa Survive",2011))[0])

    def test_negative_cache_is_short_and_expires(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"negative.json"
            resolver._write_cache(path,None)
            self.assertEqual(resolver._read_cache(path),(True,None))
            content=path.read_text()
            self.assertIn('"mbid": null',content)
            self.assertLess(resolver.NEGATIVE_TTL,resolver.POSITIVE_TTL)

    def test_existing_verified_mbid_does_not_contact_provider(self):
        async def go():
            return await resolver.missing_album_cover(
                {"title":"Blue Sky Noise","artist_name":"Circa Survive",
                 "year":2010},MB1,object(),"250")
        self.assertIsNone(asyncio.run(go()))

    def test_album_match_is_persisted_and_reused_offline(self):
        calls=[]
        class Repo:
            async def search_release_groups(self,artist,title,**kwargs):
                calls.append(("search",artist,title,kwargs))
                return [release(MB1,"Blue Sky Noise","Circa Survive",2010)]
        class Covers:
            async def get_release_group_cover(self,mbid,size,**kwargs):
                calls.append(("cover",mbid,size))
                return (b"jpeg-bytes","image/jpeg","caa")
        repo_mod=types.ModuleType("core.dependencies.repo_providers")
        repo_mod.get_musicbrainz_repository=lambda: Repo()
        priority=types.ModuleType("infrastructure.queue.priority_queue")
        priority.RequestPriority=types.SimpleNamespace(BACKGROUND_SYNC=4)
        replacements={
            "core":types.ModuleType("core"),
            "core.dependencies":types.ModuleType("core.dependencies"),
            "core.dependencies.repo_providers":repo_mod,
            "infrastructure":types.ModuleType("infrastructure"),
            "infrastructure.queue":types.ModuleType("infrastructure.queue"),
            "infrastructure.queue.priority_queue":priority,
        }
        album={"title":"Blue Sky Noise","artist_name":"Circa Survive","year":2010}
        with tempfile.TemporaryDirectory() as folder,patch.object(
            resolver,"CACHE_ROOT",Path(folder)),patch.dict(sys.modules,replacements):
            answer=asyncio.run(resolver.missing_album_cover(
                album,SYN,Covers(),"250"))
            again=asyncio.run(resolver.missing_album_cover(
                album,SYN,Covers(),"250"))
        self.assertEqual(answer,(b"jpeg-bytes","image/jpeg","caa"))
        self.assertEqual(again,answer)
        self.assertEqual(len([x for x in calls if x[0]=="search"]),1)
        self.assertEqual(len([x for x in calls if x[0]=="cover"]),2)

    def test_provider_failure_does_not_poison_cache(self):
        class Repo:
            async def search_release_groups(self,*args,**kwargs):
                raise ConnectionError("MusicBrainz offline")
        repo_mod=types.ModuleType("core.dependencies.repo_providers")
        repo_mod.get_musicbrainz_repository=lambda: Repo()
        priority=types.ModuleType("infrastructure.queue.priority_queue")
        priority.RequestPriority=types.SimpleNamespace(BACKGROUND_SYNC=4)
        replacements={
            "core":types.ModuleType("core"),
            "core.dependencies":types.ModuleType("core.dependencies"),
            "core.dependencies.repo_providers":repo_mod,
            "infrastructure":types.ModuleType("infrastructure"),
            "infrastructure.queue":types.ModuleType("infrastructure.queue"),
            "infrastructure.queue.priority_queue":priority,
        }
        with tempfile.TemporaryDirectory() as folder,patch.object(
            resolver,"CACHE_ROOT",Path(folder)),patch.dict(sys.modules,replacements):
            self.assertIsNone(asyncio.run(resolver.missing_album_cover(
                {"title":"Blue Sky Noise","artist_name":"Circa Survive",
                 "year":2010},SYN,object(),"250")))
            self.assertEqual(list(Path(folder).glob("*.json")),[])


if __name__=="__main__":
    unittest.main()
