"""Web Gaming Admin should report truthful failures without touching a real server.

All SSH, browser and TCP operations are mocked. Never invoke docker/Wolf/Caddy.
"""
import contextlib
import importlib.util
import io
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location(
    "web_admin",ROOT/"src"/"open-web-gaming-admin.py")
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
SOURCE=(ROOT/"src"/"main.c").read_text()


class Browser:
    def __init__(self, code=0):
        self.code=code
        self.argv=None
    def __call__(self, argv, **kwargs):
        self.argv=argv
        return self
    def wait(self, timeout):
        return self.code


class WebGamingAdminTests(unittest.TestCase):
    def execute(self, run_result=0, stderr="", browser_code=0,
                tcp_ok=True, browser_installed=True, existing=False):
        output=io.StringIO()
        calls=[]
        browser=Browser(browser_code)
        responses=[subprocess.CompletedProcess([],0 if existing else 255,"",""),
                   subprocess.CompletedProcess([],run_result,"",stderr)]
        def fake_run(argv, seconds):
            calls.append(argv)
            return responses.pop(0)
        def which(name):
            if name=="ssh":return "/usr/bin/ssh"
            if name=="xdg-open" and browser_installed:return "/usr/bin/xdg-open"
            return None
        class Socket:
            def __enter__(self):return self
            def __exit__(self,*args):return False
        def connect(*args, **kwargs):
            if not tcp_ok:raise ConnectionRefusedError("test fixture")
            return Socket()
        with tempfile.TemporaryDirectory() as tmp:
            with (mock.patch.object(mod, "checked_run", side_effect=fake_run),
                  mock.patch.object(mod.shutil,"which", side_effect=which),
                  mock.patch.object(mod.socket,"create_connection", side_effect=connect),
                  mock.patch.object(mod.subprocess,"Popen",side_effect=browser),
                  contextlib.redirect_stdout(output)):
                rc=mod.open_admin("100.101.32.10","owner",Path(tmp))
        return rc,output.getvalue().strip(),calls,browser.argv

    def test_new_admin_tunnel_browser_handoff_is_not_page_loaded(self):
        rc,status,calls,opened=self.execute()
        self.assertEqual(rc,0)
        self.assertEqual(status,"NOW_ADMIN_STATUS=browser_handoff_requested")
        self.assertEqual(len(calls),2)
        self.assertIn("ExitOnForwardFailure=yes",calls[1])
        self.assertTrue(opened[-1].startswith("https://127.0.0.1:"))
        self.assertTrue(opened[-1].endswith("/admin"))

    def test_existing_tunnel_reused_without_starting_another(self):
        rc,status,calls,_=self.execute(existing=True)
        self.assertEqual(rc,0)
        self.assertEqual(len(calls),1)

    def test_auth_and_unreachable_service_failures_are_actionable(self):
        cases=[
          ("Permission denied (publickey).","ssh_not_authorized"),
          ("Host key verification failed.","ssh_not_authorized"),
          ("Connection refused","server_unreachable"),
          ("Could not resolve hostname","server_name_invalid"),
          ("bind 127.0.0.1: Address already in use","local_port_unavailable"),
          ("another unexpected error","ssh_tunnel_failed"),
        ]
        for stderr,kind in cases:
            with self.subTest(kind=kind):
                rc,status,_,opened=self.execute(run_result=255,stderr=stderr)
                self.assertEqual(rc,1)
                self.assertEqual(status,"NOW_ADMIN_STATUS="+kind)
                self.assertIsNone(opened)
                self.assertNotIn("publickey",status)

    def test_no_backend_listener_missing_browser_failed_open(self):
        for overrides,kind in [
            ({"tcp_ok":False},"admin_tunnel_unreachable"),
            ({"browser_installed":False},"browser_not_installed"),
            ({"browser_code":3},"browser_launch_failed"),
        ]:
            with self.subTest(kind=kind):
                rc,status,_,_=self.execute(**overrides)
                self.assertEqual(rc,1)
                self.assertEqual(status,"NOW_ADMIN_STATUS="+kind)

    def test_invalid_settings_never_start_ssh(self):
        with tempfile.TemporaryDirectory() as tmp:
            s=io.StringIO()
            with mock.patch.object(mod,"checked_run",side_effect=AssertionError("SSH launched")),contextlib.redirect_stdout(s):
                rc=mod.open_admin("host;bad","owner",Path(tmp))
            self.assertEqual(rc,2)
            self.assertEqual(s.getvalue().strip(),"NOW_ADMIN_STATUS=invalid_settings")

    def test_gui_waits_for_helper_outcome(self):
        start=SOURCE.index("static void on_web_gaming_admin(void*w,void*p){")
        end=SOURCE.index("/* Open WebUI is",start)
        handler=SOURCE[start:end]
        self.assertIn("g_subprocess_communicate_utf8_async",handler)
        self.assertNotIn("now_launch(args)",handler)
        self.assertNotIn("OPENING WEB GAMING ADMIN VIA SSH",handler)
        self.assertIn("web_admin_finished",SOURCE)
        self.assertIn("g_subprocess_get_successful",SOURCE)
        self.assertIn("ssh_not_authorized",SOURCE)
        self.assertIn("browser_launch_failed",SOURCE)

    def test_no_unsafe_bypass_or_credentials_output(self):
        source=(ROOT/"src"/"open-web-gaming-admin.py").read_text()
        self.assertNotIn("verify=False",source)
        self.assertNotIn("--ignore-certificate-errors",source)
        self.assertNotIn("StrictHostKeyChecking=no",source)
        self.assertNotIn("stderr.strip()",source)
        self.assertNotIn('print(result.stderr)',source)
        self.assertIn('"BatchMode=yes"',source)
        self.assertIn('"StrictHostKeyChecking=accept-new"',source)

if __name__=="__main__":unittest.main()
