"""Offline integration tests: opted-in AudioDB fallback and cache safety."""
from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
PATH=ROOT/"deploy/music/bruiser_cover_fallback.py"
spec=importlib.util.spec_from_file_location("bruiser_cover_fallback",PATH)
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

MBID="6917ec0c-3d53-3835-bd9d-d079d70c1ce0"
URL="https://www.theaudiodb.com/images/media/album/test.jpg"
IMAGE=b"\xff\xd8\xff\xe0"+b"a"*20

class Album:
    title="Deja Entendu"
    artist_name="Brand New"

class Response:
    status_code=200
    headers={"content-type":"image/jpeg; charset=binary"}
    content=IMAGE

class Cover:
    def __init__(self):
        self.urls=[]
    async def _http_get(self,url,priority,source):
        self.urls.append((url,priority,source))
        return Response()

def modules(*,enabled=True,found_title="Deja Entendu",image=URL,validator=True):
    class Service:
        def is_enabled(self):
            return enabled
    class Repo:
        async def search_album_by_name(self,artist,title):
            if found_title is None:
                return None
            if artist!="Brand New" or title!="Deja Entendu":
                raise AssertionError("Bad artist/title in provider query")
            return types.SimpleNamespace(strAlbum=found_title,strAlbumThumb=image)
    dep=types.ModuleType("core.dependencies.repo_providers")
    dep.get_audiodb_image_service=lambda:Service()
    dep.get_audiodb_repository=lambda:Repo()
    val=types.ModuleType("infrastructure.validators")
    val.validate_audiodb_image_url=lambda u:validator and u==URL
    priority=types.ModuleType("infrastructure.queue.priority_queue")
    priority.RequestPriority=types.SimpleNamespace(IMAGE_FETCH=1)
    return {"core":types.ModuleType("core"),
            "core.dependencies":types.ModuleType("core.dependencies"),
            "core.dependencies.repo_providers":dep,
            "infrastructure":types.ModuleType("infrastructure"),
            "infrastructure.validators":val,
            "infrastructure.queue":types.ModuleType("infrastructure.queue"),
            "infrastructure.queue.priority_queue":priority}

class ArtworkFallbackTests(unittest.TestCase):
    def test_name_scoped_art_recovered_and_persistent_without_requery(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(
            module,"CACHE_ROOT",Path(directory)),patch.dict(
                sys.modules,modules()):
            cover=Cover()
            result=asyncio.run(module.album_name_cover(Album(),MBID,cover))
            self.assertEqual(result,(IMAGE,"image/jpeg","bruiser-audiodb-name"))
            self.assertEqual(cover.urls,[(URL,1,"audiodb")])
            saved=list(Path(directory).glob("*.img"))
            self.assertEqual(len(saved),1)
            again=asyncio.run(module.album_name_cover(Album(),MBID,object()))
            self.assertEqual(again,(IMAGE,"image/jpeg","bruiser-audiodb-name-cache"))

    def test_provider_disabled_or_improper_album_never_assigns_wrong_cover(self):
        for overrides in ({"enabled":False},{"found_title":"Deja Entendu Demos"},
                          {"found_title":None},{"image":"http://evil.example/art"},
                          {"validator":False}):
            with self.subTest(overrides=overrides),tempfile.TemporaryDirectory() as d,patch.object(
                module,"CACHE_ROOT",Path(d)),patch.dict(sys.modules,modules(**overrides)):
                self.assertIsNone(asyncio.run(module.album_name_cover(Album(),MBID,Cover())))
                self.assertEqual(list(Path(d).glob("*.img")),[])

    def test_reject_svg_or_html_even_if_claimed_jpeg(self):
        class BadCover:
            async def _http_get(self,*args,**kwargs):
                return types.SimpleNamespace(status_code=200,headers={"content-type":"image/jpeg"},
                                             content=b"<svg onload=x>")
        with tempfile.TemporaryDirectory() as d,patch.object(module,"CACHE_ROOT",Path(d)),patch.dict(
            sys.modules,modules()):
            self.assertIsNone(asyncio.run(module.album_name_cover(Album(),MBID,BadCover())))
            self.assertFalse(list(Path(d).glob("*.img")))

    def test_real_mbid_eligible_after_native_cover_failure(self):
        source=(ROOT/"deploy/music/bruiser_cover_resolver.py").read_text()
        self.assertIn("synthetic_album_id(local_id) or _valid_rg(local_id)",source)
        self.assertIn("from services.compat.bruiser_cover_fallback import album_name_cover",source)

if __name__=="__main__":
    unittest.main()
