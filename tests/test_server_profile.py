import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('profile', Path(__file__).parents[1]/'src/server-profile.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class Profiles(unittest.TestCase):
    def fixture(self, base):
        services = {'gluetun': {'env_file': [{'path':'vpn.env', 'format':'raw'}]}}
        (base/'vpn.env').write_text('PRIVATE_KEY=test-only')
        for svc, targets in {'slskd':['/app'], 'qbittorrent':['/config'], 'droppedneedle':['/app/config','/app/cache','/app/plugins','/app/imports']}.items():
            mounts=[]
            for target in targets:
                p=base/(svc+target.replace('/','-')); p.mkdir()
                (p/'fixture').write_text('state')
                if target=='/app/config': (p/'.env').write_text('DATA_ENC_KEY=test-only')
                if target=='/app/cache': (p/'library.db').write_bytes(b'test database bytes')
                mounts.append({'type':'bind','source':str(p),'target':target})
            services[svc]={'volumes':mounts}
        compose=base/'compose.json'; compose.write_text(json.dumps({'services':services}))
        return compose

    def test_roundtrip_and_refuse_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            b=Path(td); compose=self.fixture(b); output=b/'profile.tar.gz'
            calls=[]
            with patch('builtins.input', return_value='EXPORT'), patch.object(m,'run',side_effect=['slskd\ndroppedneedle','id','[]']), patch.object(m.subprocess,'run',side_effect=lambda args,**kw:calls.append(args)):
                m.export_profile(compose,output)
            self.assertEqual(calls[0][-3:],['stop','slskd','droppedneedle'])
            self.assertEqual(calls[1][-3:],['start','slskd','droppedneedle'])
            dest=b/'imported'; m.import_profile(output,dest)
            self.assertEqual((dest/'data/droppedneedle-app-config/.env').read_text(),'DATA_ENC_KEY=test-only')
            self.assertEqual(output.stat().st_mode & 0o777,0o600)
            with self.assertRaises(ValueError): m.import_profile(output,dest)

    def test_restart_after_export_error(self):
        with tempfile.TemporaryDirectory() as td:
            b=Path(td); compose=self.fixture(b); calls=[]
            with patch('builtins.input',return_value='EXPORT'), patch.object(m,'run',side_effect=['slskd','id','[]']), patch.object(m.subprocess,'run',side_effect=lambda args,**kw:calls.append(args)), patch.object(m,'digest',side_effect=OSError('disk failure')):
                with self.assertRaises(OSError): m.export_profile(compose,b/'archive')
            self.assertEqual(calls[-1][-2:],['start','slskd'])
            self.assertFalse((b/'archive').exists())

    def test_reject_traversal_and_symlink(self):
        for name,link in [('../outside',False),('link',True)]:
            with tempfile.TemporaryDirectory() as td:
                b=Path(td); archive=b/'unsafe.tar.gz'
                with tarfile.open(archive,'w:gz') as t:
                    member=tarfile.TarInfo(name)
                    if link: member.type=tarfile.SYMTYPE; member.linkname='/etc'
                    t.addfile(member,io.BytesIO())
                with self.assertRaises(ValueError): m.import_profile(archive,b/'dest')
                self.assertFalse((b/'dest').exists())

    def test_reject_checksum_mismatch(self):
        with tempfile.TemporaryDirectory() as td:
            b=Path(td); archive=b/'bad.tar.gz'
            manifest={'format':'optiplex-now-music-profile','version':1,'files':{'data/file':'bad'}}
            with tarfile.open(archive,'w:gz') as t:
                for name,value in {'manifest.json':json.dumps(manifest).encode(),'containers.json':b'[]','data/file':b'changed'}.items():
                    member=tarfile.TarInfo(name); member.size=len(value); t.addfile(member,io.BytesIO(value))
            with self.assertRaises(ValueError): m.import_profile(archive,b/'dest')
            self.assertFalse((b/'dest').exists())

if __name__=='__main__': unittest.main()
