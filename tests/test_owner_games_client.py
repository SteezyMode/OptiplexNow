"""Restricted Games SSH client tests; do not connect to live hosts."""
import contextlib
import io
from unittest.mock import patch
import importlib.util
from pathlib import Path
import os
import stat
import subprocess
import tempfile
import unittest
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location(
    "now_games_client",ROOT/"src/owner-games-client.py")
game=importlib.util.module_from_spec(spec)
spec.loader.exec_module(game)


class RestrictedGamesClientTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/"games"

    def test_creates_separate_secure_device_key_and_never_overwrites(self):
        calls=[]
        def fake_keygen(argv,**kwargs):
            calls.append(list(argv))
            (self.path/"id_ed25519").write_bytes(b"PRIVATE TEST KEY")
            (self.path/"id_ed25519").chmod(0o600)
            (self.path/"id_ed25519.pub").write_text("ssh-ed25519 PUBLIC_TEST")
            (self.path/"id_ed25519.pub").chmod(0o644)
            return SimpleNamespace(returncode=0)
        private,public=game.ensure_key(self.path,keygen=fake_keygen)
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode),0o700)
        self.assertEqual(stat.S_IMODE(private.stat().st_mode),0o600)
        self.assertEqual(stat.S_IMODE(public.stat().st_mode),0o644)
        self.assertEqual(len(calls),1)
        game.ensure_key(self.path,keygen=fake_keygen)
        self.assertEqual(len(calls),1)

    def test_refuses_partial_loose_and_linked_keys(self):
        self.path.mkdir(mode=0o700)
        (self.path/"id_ed25519").write_text("private")
        (self.path/"id_ed25519").chmod(0o600)
        with self.assertRaisesRegex(ValueError,"Partial"):
            game.ensure_key(self.path)
        (self.path/"id_ed25519.pub").write_text("public")
        (self.path/"id_ed25519.pub").chmod(0o644)
        (self.path/"id_ed25519").chmod(0o644)
        with self.assertRaisesRegex(ValueError,"unsafe"):
            game.ensure_key(self.path)
        (self.path/"id_ed25519").chmod(0o600)
        (self.path/"id_ed25519").unlink()
        (self.path/"id_ed25519").symlink_to(self.path/"id_ed25519.pub")
        with self.assertRaisesRegex(ValueError,"symlink"):
            game.ensure_key(self.path)

    def test_ssh_request_uses_only_fixed_options_no_remote_command(self):
        self.path.mkdir(mode=0o700)
        private=self.path/"id_ed25519"
        private.write_bytes(b"private")
        private.chmod(0o600)
        commands=[]
        def run(argv,**kwargs):
            commands.append((list(argv),kwargs))
            return SimpleNamespace(returncode=0,stdout=b'{"success":true,"status":"wolf_ui_connected"}')
        out=game.invoke("100.121.156.34","optiplex","status",
                        key_dir=self.path,runner=run)
        self.assertEqual(out["status"],"wolf_ui_connected")
        argv,kw=commands[0]
        self.assertEqual(argv[:4],["ssh","-F","/dev/null","-i"])
        self.assertEqual(argv[-4:],["-l","optiplex","--","100.121.156.34"])
        self.assertNotIn("docker",str(argv))
        self.assertNotIn("owner_games_ssh.py",str(argv))
        self.assertIn("StrictHostKeyChecking=yes",argv)
        self.assertIn("IdentitiesOnly=yes",argv)
        self.assertIn("BatchMode=yes",argv)
        self.assertEqual(kw["input"],b'{"version":1,"action":"status"}\n')
        self.assertEqual(kw["timeout"],25)

    def test_ui_mode_emits_one_safe_token_and_denies_failure(self):
        with patch.object(game, "invoke",
                          return_value={"success": True, "status": "joined"}):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(game.main(
                    ["--ui", "start", "127.0.0.1", "owner"]), 0)
            self.assertEqual(out.getvalue(), "joined\\n".replace("\\\\n", "\\n"))
        with patch.object(game, "invoke",
                          side_effect=RuntimeError("PRIVATE HOST DETAIL")):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(game.main(
                    ["--ui", "status", "127.0.0.1", "owner"]), 1)
            self.assertEqual(out.getvalue(), "unavailable\\n".replace("\\\\n", "\\n"))
            self.assertNotIn("PRIVATE", out.getvalue())

    def test_rejects_invalid_destination_and_response(self):
        for host in ("--ProxyCommand=x","a..b","bad host"):
            with self.assertRaises(ValueError):
                game.validated_target(host,"optiplex")
        for user in ("-root","foo;sh"):
            with self.assertRaises(ValueError):
                game.validated_target("host",user)
        self.path.mkdir(mode=0o700)
        (self.path/"id_ed25519").write_bytes(b"private")
        (self.path/"id_ed25519").chmod(0o600)
        def result(blob=b'{"success":false,"status":"denied"}',code=0):
            return lambda *a,**kw:SimpleNamespace(returncode=code,stdout=blob)
        for run in (result(),result(b'{"success":true,"pin":[1,2]}'),
                    result(b"not json"),result(b"a"*2049),result(code=1)):
            with self.subTest(run=run):
                with self.assertRaises(RuntimeError):
                    game.invoke("host","user","start",key_dir=self.path,
                                runner=run)
        with self.assertRaises(ValueError):
            game.invoke("host","user","exec",key_dir=self.path,
                        runner=result())


if __name__=="__main__":
    unittest.main()
