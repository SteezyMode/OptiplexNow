"""End-to-end *helper-protocol* simulation for NOW's Beta 1 client.

Runs the real packaged-source Tailscale status/discovery, SSH key-enrollment,
Wolf SSH client and Wolf host helper as separate subprocesses. Only fake CLI
executables stand in for tailscaled, ssh-copy-id, SSH and Docker/Wolf.

No privileged operations, real servers, credentials, remote networking or
GTK automation. Physical-device acceptance remains a separate release gate.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
SOURCE = REPO / "src"
FAKE_CLI = REPO / "tests" / "fixtures" / "onboarding_mock_cli.py"
# Loopback stand-in ensures any candidate port hint probes remain local.
HOST = "127.0.0.2"
SELF = "100.64.9.1"
USER = "testuser"


class OnboardingFlowTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="now-onboarding-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.home = self.root / "home"
        self.bin = self.root / "bin"
        self.home.mkdir()
        self.bin.mkdir()
        for executable in ("tailscale", "ssh-copy-id", "ssh", "docker"):
            (self.bin / executable).symlink_to(FAKE_CLI)
        askpass = self.root / "fake-askpass"
        askpass.write_text("#!/bin/sh\nexit 1\n")
        askpass.chmod(0o700)
        self.env = os.environ.copy()
        self.env.update({
            "HOME": str(self.home),
            "XDG_CONFIG_HOME": str(self.home / ".config"),
            "PATH": str(self.bin) + os.pathsep + os.environ.get("PATH", ""),
            "NOW_TEST_FIXTURE_ROOT": str(self.root),
            "NOW_TEST_HOST_HELPER": str(SOURCE / "wolf-pair-local.py"),
            "DISPLAY": ":99",  # Askpass is mocked, never launched.
        })
        self.env.pop("NOW_MOCK_AUTH_DENIED", None)
        self.env.pop("NOW_MOCK_SSH_UNREACHABLE", None)
        self.env.pop("NOW_MOCK_WOLF_DENIED", None)

    def save(self, filename, value):
        (self.root / filename).write_text(json.dumps(value))

    def read_log(self, name):
        path = self.root / name
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def invoke(self, helper, *args, payload=None, overrides=None):
        env = self.env.copy()
        if overrides:
            env.update(overrides)
        proc = subprocess.run(
            [sys.executable, str(SOURCE / helper), *args],
            input=json.dumps(payload) if payload is not None else None,
            text=True, capture_output=True, env=env, timeout=24,
            check=False
        )
        self.assertNotIn("fictional-private-secret", proc.stdout)
        return proc

    def connected_tailnet(self):
        self.save("tailnet.json", {
            "BackendState": "Running",
            "Self": {"TailscaleIPs": [SELF]},
            "Peer": {
                "server": {"Online": True, "HostName": "example-host",
                           "TailscaleIPs": [HOST]},
                "old": {"Online": False, "HostName": "offline-device",
                        "TailscaleIPs": ["100.64.9.4"]},
            }
        })

    def pending_device(self, ip=HOST):
        self.save("pending.json", [
            {"client_ip": ip, "pair_secret": "fictional-private-secret"}
        ])

    def test_first_run_sign_in_discovery_authorize_pair_and_reconnect(self):
        # Start with a disposable account: no NOW config and no SSH identity.
        self.assertFalse((self.home / ".config" / "optiplex-desk").exists())
        self.save("tailnet.json", {"BackendState": "NeedsLogin"})
        status = self.invoke("tailscale-status.py")
        self.assertEqual((status.returncode, status.stdout.strip()), (0, "SIGN_IN"))
        self.assertNotEqual(self.invoke("find-servers.py").returncode, 0)
        self.assertFalse((self.root / "authorized.json").exists())

        # Account becomes connected: the real discovery script lists its peer.
        self.connected_tailnet()
        self.assertEqual(self.invoke("tailscale-status.py").stdout.strip(), "CONNECTED")
        found = self.invoke("find-servers.py")
        self.assertEqual(found.returncode, 0, found.stdout + found.stderr)
        self.assertIn(HOST + "\t", found.stdout)
        self.assertNotIn(SELF + "\t", found.stdout)

        # Real key-generation and authorization bridge, fake ssh-copy-id only.
        enrolled = self.invoke("ssh-authorize.py", HOST, USER)
        self.assertEqual(enrolled.returncode, 0, enrolled.stdout + enrolled.stderr)
        self.assertEqual(enrolled.stdout.strip(), "AUTHORIZED")
        key = self.home / ".ssh" / "id_ed25519"
        self.assertTrue(key.is_file())
        self.assertEqual(key.stat().st_mode & 0o077, 0)
        original_key = key.read_bytes()
        self.assertEqual(self.read_log("copy-id.jsonl")[0]["host"], f"{USER}@{HOST}")

        self.pending_device()
        pending = self.invoke("wolf-pair-client.py", "pending-text", HOST, USER)
        self.assertEqual((pending.returncode, pending.stdout.strip()),
                         (0, "1\t" + HOST))
        self.assertNotIn("pair_secret", pending.stdout)

        paired = self.invoke("wolf-pair-client.py", "pair", HOST, USER,
                             payload={"index": 1, "client_ip": HOST, "pin": "0123"})
        self.assertEqual(paired.returncode, 0, paired.stdout + paired.stderr)
        self.assertTrue(json.loads(paired.stdout)["success"])
        self.assertEqual(len(self.read_log("wolf-post.jsonl")), 1)
        self.assertEqual(json.loads((self.root / "pending.json").read_text()), [])

        # Retry and reconnect: the existing local key is never replaced.
        self.assertEqual(self.invoke("ssh-authorize.py", HOST, USER).returncode, 0)
        self.assertEqual(key.read_bytes(), original_key)
        self.assertEqual(self.invoke("wolf-pair-client.py",
                                     "pending-text", HOST, USER).stdout, "")
        self.assertTrue(all(row["strict"] for row in self.read_log("ssh.jsonl")))
        self.assertFalse((self.home / ".config" / "optiplex-desk").exists())

    def test_stale_or_changed_wolf_identity_never_authorizes(self):
        self.connected_tailnet()
        self.pending_device()
        first = self.invoke("wolf-pair-client.py", "pending-text", HOST, USER)
        self.assertEqual(first.stdout.strip(), "1\t" + HOST)
        self.pending_device(ip="127.0.0.3")  # Changed after discovery.
        pairing = self.invoke("wolf-pair-client.py", "pair", HOST, USER,
                              payload={"index": 1, "client_ip": HOST, "pin": "0123"})
        self.assertNotEqual(pairing.returncode, 0)
        self.assertFalse(json.loads(pairing.stdout)["success"])
        self.assertEqual(self.read_log("wolf-post.jsonl"), [])

    def test_ssh_and_wolf_refusals_fail_closed_then_recover(self):
        self.connected_tailnet()
        denied = self.invoke("ssh-authorize.py", HOST, USER,
                             overrides={"NOW_MOCK_AUTH_DENIED": "1"})
        self.assertNotEqual(denied.returncode, 0)
        self.assertNotIn("AUTHORIZED\n", denied.stdout)
        self.assertFalse((self.root / "authorized.json").exists())
        self.assertEqual(self.invoke("ssh-authorize.py", HOST, USER).returncode, 0)

        unreachable = self.invoke("wolf-pair-client.py", "pending-text", HOST, USER,
                                  overrides={"NOW_MOCK_SSH_UNREACHABLE": "1"})
        self.assertNotEqual(unreachable.returncode, 0)
        self.assertFalse(json.loads(unreachable.stdout)["success"])

        self.pending_device()
        refused = self.invoke("wolf-pair-client.py", "pair", HOST, USER,
                              payload={"index": 1, "client_ip": HOST, "pin": "9876"},
                              overrides={"NOW_MOCK_WOLF_DENIED": "1"})
        self.assertNotEqual(refused.returncode, 0)
        self.assertFalse(json.loads(refused.stdout)["success"])
        self.assertEqual(len(json.loads((self.root / "pending.json").read_text())), 1)

        recovered = self.invoke("wolf-pair-client.py", "pair", HOST, USER,
                                payload={"index": 1, "client_ip": HOST, "pin": "9876"})
        self.assertEqual(recovered.returncode, 0, recovered.stdout + recovered.stderr)
        self.assertTrue(json.loads(recovered.stdout)["success"])


if __name__ == "__main__":
    unittest.main()
