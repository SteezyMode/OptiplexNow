"""Offline forced-command SSH Games bridge tests. No live SSH or Docker."""
import base64
import json
import os
from pathlib import Path
import stat
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "server"))
sys.path.insert(0, str(ROOT / "tests"))

from owner_access import OwnerStore, PolicyError
from owner_games_ssh import (_read_private_config, _request_line, execute,
                             host_writer_preflight)
from owner_games_enroll import authorized_line, validated_ed25519_public, prepare_entry
from test_owner_launch import StatefulWolf
from test_owner_lobby import fixtures


def ed25519_key():
    name = b"ssh-ed25519"
    body = struct.pack("!I", len(name)) + name + struct.pack("!I", 32) + b"x"*32
    return "ssh-ed25519 " + base64.b64encode(body).decode() + " client-name"


class ForcedGamesBridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.store = OwnerStore(str(self.base / "owner"))
        with self.store.locked() as fd:
            self.store.write(fd, fixtures()[0])
        self.api = StatefulWolf()
        self.config = {
            "version": 1, "state_dir": self.store.directory,
            "video_caps": "video/x-raw",
            "enabled": True, "legacy_links_reviewed": True,
        }
        self.env = {"SSH_CONNECTION": "127.0.0.1 5555 127.0.0.1 22"}
        self.handler = lambda action: execute(
            verified_client_id="1001", environ=self.env,
            read_request=lambda: {"version": 1, "action": action},
            read_config=lambda: self.config,
            wolf_api_factory=lambda: self.api, writer_check=lambda: True)

    def test_forced_session_status_start_stop_start(self):
        self.assertEqual(self.handler("status")["status"], "wolf_ui_connected")
        self.assertEqual(self.handler("start")["status"], "joined")
        self.assertEqual(self.handler("status")["status"], "in_use")
        self.assertEqual(self.handler("stop")["status"], "idle")
        self.assertEqual(self.handler("start")["status"], "joined")
        self.assertEqual([p for m,p,_ in self.api.calls if m == "POST"],[
            "/api/v1/lobbies/create", "/api/v1/lobbies/join",
            "/api/v1/lobbies/stop", "/api/v1/lobbies/create",
            "/api/v1/lobbies/join"])

    def test_forced_key_observe_is_read_only_until_actual_runner_exit(self):
        self.assertEqual(self.handler("start")["status"], "joined")
        previous_posts = [p for m, p, _ in self.api.calls if m == "POST"]
        self.assertEqual(self.handler("observe")["status"], "running")
        self.api.lobby = None
        self.assertEqual(self.handler("observe")["status"], "finished")
        self.assertEqual(previous_posts,
                         [p for m, p, _ in self.api.calls if m == "POST"])
        # Only later idle reconciliation archives the lease.
        self.assertEqual(self.handler("status")["status"], "in_use")

    def test_env_denies_non_ssh_and_remote_exec(self):
        for env in ({}, {"SSH_CONNECTION": "x", "SSH_ORIGINAL_COMMAND": "sh"},
                    {"SSH_CONNECTION": "x", "SSH_ORIGINAL_COMMAND": "status"}):
            with self.subTest(env=env):
                with self.assertRaisesRegex(PolicyError, "Restricted"):
                    execute(verified_client_id="1001", environ=env,
                            read_request=lambda: {"version":1,"action":"start"},
                            read_config=lambda: self.config,
                            wolf_api_factory=lambda:self.api, writer_check=lambda:True)
        self.assertFalse(any(m=="POST" for m,_,_ in self.api.calls))

    def test_wrong_ssh_bound_client_denied(self):
        with self.assertRaisesRegex(PolicyError,"not paired"):
            execute(verified_client_id="1002", environ=self.env,
                    read_request=lambda:{"version":1,"action":"start"},
                    read_config=lambda:self.config,
                    wolf_api_factory=lambda:self.api, writer_check=lambda:True)
        self.assertFalse(any(m=="POST" for m,_,_ in self.api.calls))

    def test_disabled_host_config_denies_mutation(self):
        self.config["enabled"] = False
        with self.assertRaisesRegex(PolicyError,"not enabled"):
            self.handler("start")
        self.config["enabled"] = True
        self.config["legacy_links_reviewed"] = False
        with self.assertRaisesRegex(PolicyError,"not enabled"):
            self.handler("start")
        self.assertEqual(self.handler("status")["status"],"wolf_ui_connected")

    def test_host_config_enforces_mode_schema_and_no_symlink(self):
        directory = self.base / "settings"
        directory.mkdir(mode=0o700)
        target = directory / "owner-games-host.json"
        target.write_text(json.dumps(self.config))
        target.chmod(0o600)
        self.assertEqual(_read_private_config(target),self.config)
        target.chmod(0o644)
        with self.assertRaisesRegex(PolicyError,"permissions"):
            _read_private_config(target)
        target.chmod(0o600)
        for invalid in (
            {**self.config, "enabled": "true"},
            {**self.config, "video_caps": "video/x-raw(memory:Unknown)"},
            {**self.config, "client_id": "1002"},
            {**self.config, "state_dir": "relative/path"},
        ):
            target.write_text(json.dumps(invalid))
            with self.assertRaises(PolicyError):
                _read_private_config(target)
        target.unlink()
        (directory/"source").write_text(json.dumps(self.config))
        target.symlink_to(directory/"source")
        with self.assertRaises(OSError):
            _read_private_config(target)

    def test_request_input_rejects_double_command_and_large_payload(self):
        for data,expected in (
            (b'{"version":1,"action":"status"}\n',{"version":1,"action":"status"}),
            (b'{"version":1,"action":"status"}\n{"action":"stop"}\n',"Multiple"),
            (b"f"*280+b"\n","exceeds"),
            (b'{"version":1,"action":"bad"\n',"Invalid"),
        ):
            read,write=os.pipe()
            try:
                os.write(write,data)
                os.close(write);write=-1
                if isinstance(expected,dict):
                    self.assertEqual(_request_line(read),expected)
                else:
                    with self.assertRaisesRegex(PolicyError,expected):
                        _request_line(read)
            finally:
                os.close(read)
                if write!=-1: os.close(write)

    def test_host_writer_preflight_denies_steam_and_containers(self):
        with patch("owner_games_ssh._capture", side_effect=["kworker\nbash\n","wolf\njellyfin\n"]):
            self.assertTrue(host_writer_preflight())
        with patch("owner_games_ssh._capture",return_value="steamwebhelper\n"):
            self.assertFalse(host_writer_preflight())
        with patch("owner_games_ssh._capture",side_effect=["bash\n","WolfSteam-123\n"]):
            self.assertFalse(host_writer_preflight())
        with patch("owner_games_ssh._capture",side_effect=OSError("PRIVATE")):
            with self.assertRaises(OSError):
                host_writer_preflight()

    def test_verified_authorized_key_forced_command_generation(self):
        public=ed25519_key()
        line=authorized_line(public,"1001","/opt/optiplex-now/server/owner_games_ssh.py")
        self.assertIn('restrict,command="/usr/bin/python3 /opt/optiplex-now/server/owner_games_ssh.py --client-id 1001"',line)
        self.assertEqual(line.split(" ssh-ed25519 ")[1],public.split(" ",1)[1].split(" ")[0])
        self.assertNotIn("client-name",line)
        self.assertNotIn("password",line)
        with self.assertRaises(PolicyError):
            authorized_line(public,"1;rm -rf /","/opt/script.py")
        with self.assertRaises(PolicyError):
            authorized_line(public,"1001",'/opt/evil"command')
        with self.assertRaises(PolicyError):
            authorized_line("ssh-rsa AAAA", "1001", "/opt/script.py")
        with self.assertRaises(PolicyError):
            validated_ed25519_public("ssh-ed25519 AAAA")

    def test_enrollment_requires_independent_owner_confirmation_and_grant(self):
        public=ed25519_key()
        script=ROOT/"server/owner_games_ssh.py"
        with self.assertRaisesRegex(PolicyError,"approval"):
            prepare_entry(public,client_id="1001",store=self.store,
                          wolf_api=self.api,script_path=script)
        line=prepare_entry(public,client_id="1001",store=self.store,
                           wolf_api=self.api,script_path=script,approved=True)
        self.assertIn("--client-id 1001",line)
        with self.assertRaises(PolicyError):
            prepare_entry(public,client_id="1002",store=self.store,
                          wolf_api=self.api,script_path=script,approved=True)


if __name__=="__main__":
    unittest.main()
