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
            b=Path(td); compose=self.fixture(b); output=b/'profile.bmprofile'
            calls=[]
            with patch('builtins.input', return_value='EXPORT'), patch.object(m,'run',side_effect=['slskd\ndroppedneedle','id','[]']), patch.object(m.subprocess,'run',side_effect=lambda args,**kw:calls.append(args)):
                m.export_profile(compose,output,passphrase='fixture-recovery-passphrase-123456')
            self.assertEqual(calls[0][-3:],['stop','slskd','droppedneedle'])
            self.assertEqual(calls[1][-3:],['start','slskd','droppedneedle'])
            dest=b/'imported'; m.import_profile(output,dest,passphrase='fixture-recovery-passphrase-123456')
            self.assertEqual((dest/'data/droppedneedle-app-config/.env').read_text(),'DATA_ENC_KEY=test-only')
            self.assertEqual(output.stat().st_mode & 0o777,0o600)
            self.assertTrue(m.is_encrypted(output))
            ciphertext=output.read_bytes()
            self.assertNotIn(b'test database bytes',ciphertext)
            self.assertNotIn(b'PRIVATE_KEY=test-only',ciphertext)
            self.assertNotIn(b'DATA_ENC_KEY=test-only',ciphertext)
            self.assertNotIn(b'containers.json',ciphertext)
            with self.assertRaises(ValueError): m.import_profile(output,dest,passphrase='fixture-recovery-passphrase-123456')

    def test_wrong_passphrase_and_corruption_never_stage_plaintext(self):
        with tempfile.TemporaryDirectory() as td:
            b = Path(td)
            compose = self.fixture(b)
            output = b/'safe.bmprofile'
            with patch('builtins.input',return_value='EXPORT'), \
                 patch.object(m,'run',return_value=''), \
                 patch.object(m.subprocess,'run'):
                m.export_profile(compose,output,passphrase='fixture-recovery-passphrase-123456')
            for name, wrong, corrupt in (
                ('wrong',True,False), ('tampered',False,True)
            ):
                candidate = b/(name+'.bmprofile')
                candidate.write_bytes(output.read_bytes())
                if corrupt:
                    data=bytearray(candidate.read_bytes())
                    data[-20] ^= 0xFF
                    candidate.write_bytes(data)
                dest=b/('import-'+name)
                with self.assertRaises(ValueError):
                    m.import_profile(candidate,dest,passphrase=(
                        'incorrect-recovery-passphrase-123' if wrong
                        else 'fixture-recovery-passphrase-123456'))
                self.assertFalse(dest.exists())
                self.assertFalse(list(b.glob('.verified-music-*')))

    def test_legacy_import_explicit_only_and_does_not_convert_existing_file(self):
        with tempfile.TemporaryDirectory() as td:
            b=Path(td)
            archive=b/'legacy.tar.gz'
            manifest={'format':'optiplex-now-music-profile','version':1,
                      'files':{'data/example':m.hashlib.sha256(b'old').hexdigest()},
                      'directories':[]}
            with tarfile.open(archive,'w:gz') as tar:
                for name,payload in (
                    ('manifest.json',json.dumps(manifest).encode()),
                    ('containers.json',b'[]'),
                    ('data/example',b'old'),
                ):
                    member=tarfile.TarInfo(name)
                    member.size=len(payload)
                    tar.addfile(member,io.BytesIO(payload))
            with self.assertRaisesRegex(ValueError,'Explicit legacy recovery'):
                m.import_profile(archive,b/'out')
            m.import_profile(archive,b/'out',allow_legacy_plaintext=True)
            self.assertEqual((b/'out/data/example').read_bytes(),b'old')
            self.assertTrue(archive.read_bytes().startswith(b'\x1f\x8b'))

    def test_export_requires_encrypted_extension_before_any_docker_action(self):
        with tempfile.TemporaryDirectory() as td:
            b=Path(td); compose=self.fixture(b)
            with patch.object(m,'run') as docker:
                with self.assertRaisesRegex(ValueError,'bmprofile'):
                    m.export_profile(compose,b/'unsafe.tar.gz',
                                     passphrase='fixture-recovery-passphrase-123456')
                docker.assert_not_called()

    def test_restart_after_export_error(self):
        with tempfile.TemporaryDirectory() as td:
            b=Path(td); compose=self.fixture(b); calls=[]
            with patch('builtins.input',return_value='EXPORT'), patch.object(m,'run',side_effect=['slskd','id','[]']), patch.object(m.subprocess,'run',side_effect=lambda args,**kw:calls.append(args)), patch.object(m,'digest',side_effect=OSError('disk failure')):
                with self.assertRaises(OSError): m.export_profile(compose,b/'archive.bmprofile',passphrase='fixture-recovery-passphrase-123456')
            self.assertEqual(calls[-1][-2:],['start','slskd'])
            self.assertFalse((b/'archive.bmprofile').exists())

    def test_reject_traversal_and_symlink(self):
        for name,link in [('../outside',False),('link',True)]:
            with tempfile.TemporaryDirectory() as td:
                b=Path(td); archive=b/'unsafe.tar.gz'
                with tarfile.open(archive,'w:gz') as t:
                    member=tarfile.TarInfo(name)
                    if link: member.type=tarfile.SYMTYPE; member.linkname='/etc'
                    t.addfile(member,io.BytesIO())
                with self.assertRaises(ValueError): m.import_profile(archive,b/'dest',allow_legacy_plaintext=True)
                self.assertFalse((b/'dest').exists())

    def test_reject_checksum_mismatch(self):
        with tempfile.TemporaryDirectory() as td:
            b=Path(td); archive=b/'bad.tar.gz'
            manifest={'format':'optiplex-now-music-profile','version':1,'files':{'data/file':'bad'}}
            with tarfile.open(archive,'w:gz') as t:
                for name,value in {'manifest.json':json.dumps(manifest).encode(),'containers.json':b'[]','data/file':b'changed'}.items():
                    member=tarfile.TarInfo(name); member.size=len(value); t.addfile(member,io.BytesIO(value))
            with self.assertRaises(ValueError): m.import_profile(archive,b/'dest',allow_legacy_plaintext=True)
            self.assertFalse((b/'dest').exists())

if __name__=='__main__': unittest.main()
