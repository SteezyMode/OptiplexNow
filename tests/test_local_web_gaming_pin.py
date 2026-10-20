"""Local owner Web Gaming PIN flow: no network or Docker changes in tests."""
import importlib.util
from pathlib import Path
import socket
import subprocess
import tempfile
import unittest
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("owner_pin",ROOT/"src"/"local-web-gaming-pin.py")
pin=importlib.util.module_from_spec(spec)
spec.loader.exec_module(pin)
MAIN=(ROOT/"src"/"main.c").read_text()


class OwnerWebGamingPinTests(unittest.TestCase):
    def test_pin_parser_accepts_only_six_digits_or_upstream_label(self):
        self.assertEqual(pin.parse_pin("123456\n"),"123456")
        self.assertEqual(pin.parse_pin("Access PIN: 000123\n"),"000123")
        for bad in ("", "PIN: 12345", "PIN: 1234567",
                    "Access PIN: 123456 and backup PIN: 987654",
                    "Status: 123456", "0"*5000):
            with self.subTest(bad=bad[:40]):
                self.assertIsNone(pin.parse_pin(bad))

    def run_with_socket(self, inspection, issuance=None):
        commands=[]
        def fake_run(argv,**kw):
            commands.append((argv,kw))
            if len(commands)==1:return inspection
            return issuance or SimpleNamespace(returncode=0,stdout="Access PIN: 240619\n",stderr="")
        with tempfile.TemporaryDirectory() as tmp:
            with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as sock:
                address=str(Path(tmp)/"docker.sock")
                sock.bind(address)
                outcome=pin.issue_pin(which=lambda exe:"/usr/bin/docker" if exe=="docker" else None,
                                      runner=fake_run,socket_path=address)
        return outcome,commands

    def test_authorized_local_owner_only_uses_upstream_nonrevoking_cli(self):
        outcome,calls=self.run_with_socket(SimpleNamespace(returncode=0,stdout="true\n",stderr=""))
        self.assertEqual(outcome,(0,"pin:240619"))
        self.assertEqual(len(calls),2)
        self.assertEqual(calls[0][0][-5:],["inspect","--type","container","--format","{{.State.Running}}","moonlightweb"][-5:])
        self.assertEqual(calls[1][0][-4:],["exec","moonlightweb","moonlightweb","--new-pin"])
        self.assertTrue(all(argv[:2]==["/usr/bin/docker","--host"] and argv[2].startswith("unix://") for argv,_ in calls))
        self.assertNotIn("--auth-key",str(calls))
        self.assertNotIn("sudo",str(calls))
        self.assertNotIn("pkexec",str(calls))
        self.assertNotIn("auth/regenerate",str(calls))
        self.assertTrue(all(k["timeout"]<=12 for _,k in calls))

    def test_no_local_socket_no_remote_docker_action(self):
        called=[]
        outcome=pin.issue_pin(which=lambda name:called.append(name),socket_path="/this/sock/does/not/exist")
        self.assertEqual(outcome,(1,"not_local_server"))
        self.assertEqual(called,[])

    def test_untrusted_status_and_failures(self):
        for result,expected in [
            (SimpleNamespace(returncode=1,stdout="",stderr="permission denied"),"docker_permission_denied"),
            (SimpleNamespace(returncode=1,stdout="",stderr="not found"),"moonlightweb_not_found"),
            (SimpleNamespace(returncode=0,stdout="false\n",stderr=""),"moonlightweb_not_running"),
        ]:
            with self.subTest(expected=expected):
                outcome,calls=self.run_with_socket(result)
                self.assertEqual(outcome,(1,expected))
                self.assertEqual(len(calls),1)

    def test_upstream_failure_or_invalid_output_not_shown(self):
        inspect=SimpleNamespace(returncode=0,stdout="true\n",stderr="")
        for resp,expected in [
          (SimpleNamespace(returncode=1,stdout="",stderr="secret admin output"),"pin_issuance_failed"),
          (SimpleNamespace(returncode=0,stdout="unexpected response",stderr=""),"pin_output_unrecognized"),
        ]:
            outcome,_=self.run_with_socket(inspect,resp)
            self.assertEqual(outcome,(1,expected))

    def test_gui_owner_only_no_ssh_and_client_login_unmodified(self):
        self.assertIn('ISSUE WEB GAMING ACCESS PIN (THIS SERVER)',MAIN)
        self.assertIn('if(access("/var/run/docker.sock",F_OK)==0)',MAIN)
        start=MAIN.index("static void on_web_gaming_issue_pin(")
        end=MAIN.index("static void on_web_gaming_admin(",start)
        handler=MAIN[start:end]
        self.assertIn("g_subprocess_communicate_utf8_async",handler)
        self.assertIn("ISSUE PIN",handler)
        self.assertNotIn("terminal_launch(",handler)
        self.assertNotIn("sudo",handler)
        self.assertNotIn('"ssh"',handler)
        self.assertIn('"https://games.monumentrisk.com"',MAIN)
        self.assertIn("gtk_label_set_selectable",MAIN[MAIN.index("static void owner_pin_finished("):start])

if __name__=="__main__": unittest.main()
