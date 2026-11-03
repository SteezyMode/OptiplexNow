"""Offline dual-search plugin manager safety contract; no Docker/Internet calls."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/manage_dual_search.py"
spec = importlib.util.spec_from_file_location("bruiser_dual_manager_test", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class FakeAPI:
    def __init__(self):
        self.state = {"bruiser_apibay":True,"torrentscsv":False,"limetorrents":False}
        self.installed = {}
        self.calls = []

    def plugins(self):
        return {name: {"name":name,"enabled":enabled,"version":"1"}
                for name,enabled in self.state.items()}

    def call(self, action, fields=None):
        self.calls.append((action,fields))
        if action == "installPlugin":
            name = fields["sources"].rsplit("/",1)[-1].removesuffix(".py")
            self.state[name] = True
            self.installed[name] = True
        elif action == "uninstallPlugin":
            self.state.pop(fields["names"],None)
        return b""

    def enable(self, name, enabled):
        self.calls.append(("enable",(name,enabled)))
        if name in self.state:
            self.state[name]=enabled

    def wait_for_hash(self,name,sha,timeout=12):
        self.calls.append(("wait_for_hash",(name,sha)))
        return self.installed.get(name,False)

    def test_search(self,name,category,pattern):
        self.calls.append(("test_search",(name,category,pattern)))
        return 12


class ManagerTests(unittest.TestCase):
    def test_exact_pinned_source_matches_packaged_engines(self):
        for name, sha in mod.SOURCE_BLOBS.items():
            file = ROOT / "server/search_plugins" / (name + ".py")
            self.assertEqual(mod.blob_hash(file.read_bytes()), sha)

    def test_default_checks_without_mutating(self):
        api=FakeAPI()
        self.assertEqual(api.state["bruiser_apibay"],True)
        self.assertEqual(api.calls,[])

    def test_apply_verifies_sources_before_any_plugin_change(self):
        api=FakeAPI()
        saved=[]
        old=mod.blob_hash
        def source_hash(raw):
            return mod.OLD_API_BAY if raw == b"PRIOR" else old(raw)
        patches=[
            patch.object(mod,"installed_bytes",side_effect=lambda n:
                         b"PRIOR" if n=="bruiser_apibay" else None),
            patch.object(mod,"blob_hash",side_effect=source_hash),
            patch.object(mod,"verified_source",
                         side_effect=lambda n: ("https://raw.example/"+n+".py",b"fixture")),
            patch.object(mod,"nova_test",return_value=3),
            patch.object(mod,"save_backup",side_effect=lambda *args:saved.append(args)),
            patch.object(mod,"BACKUP",Path("/unlikely-path-does-not-exist-dual-search")),
        ]
        with patches[0],patches[1],patches[2],patches[3],patches[4],patches[5]:
            mod.apply(api)
        self.assertEqual(len(saved),1)
        self.assertEqual(saved[0][0],b"PRIOR")
        self.assertEqual(api.state["bruiser_apibay"],True)
        self.assertEqual(api.state["bruiser_bitsearch"],True)
        self.assertEqual(api.state["torrentscsv"],False)
        self.assertEqual(api.state["limetorrents"],False)
        self.assertEqual(sum(1 for action,_ in api.calls if action=="installPlugin"),2)
        self.assertEqual(sum(1 for action,_ in api.calls if action=="test_search"),2)
        # An unrelated plugin cannot be enabled by the installer.
        self.assertEqual(set(api.state),{"bruiser_apibay","bruiser_bitsearch",
                                         "torrentscsv","limetorrents"})

    def test_source_fetch_failure_makes_no_changes(self):
        api=FakeAPI()
        old=mod.blob_hash
        with patch.object(mod,"installed_bytes",return_value=b"PRIOR"),\
             patch.object(mod,"blob_hash",side_effect=lambda raw:
                mod.OLD_API_BAY if raw==b"PRIOR" else old(raw)),\
             patch.object(mod,"BACKUP",Path("/unlikely-path-does-not-exist-dual-search")) ,\
             patch.object(mod,"verified_source",
                          side_effect=mod.InstallError("untrusted source")):
            with self.assertRaises(mod.InstallError):
                mod.apply(api)
        self.assertFalse(api.calls)

    def test_bitsearch_collision_is_rejected_without_mutation(self):
        api=FakeAPI()
        api.state["bruiser_bitsearch"]=True
        old=mod.blob_hash
        with patch.object(mod,"installed_bytes",side_effect=lambda n:
                     b"PRIOR" if n=="bruiser_apibay" else b"EXISTING"),\
             patch.object(mod,"blob_hash",side_effect=lambda raw:
                mod.OLD_API_BAY if raw==b"PRIOR" else old(raw)):
            with self.assertRaisesRegex(mod.InstallError,"already installed"):
                mod.apply(api)
        self.assertFalse(api.calls)

    def test_rollback_will_refuse_unrecognized_sources(self):
        api=FakeAPI()
        with patch.object(mod,"read_backup",return_value=(
                    {"bruiser_apibay":True},Path("/tmp/old.py"))),\
             patch.object(mod,"installed_bytes",return_value=b"UNEXPECTED"):
            with self.assertRaises(mod.InstallError):
                mod.rollback(api)
        self.assertFalse(api.calls)


if __name__ == "__main__":
    unittest.main()
