"""Web Gaming Admin launch/pairing regression fixtures. No actual SSH or browser."""
import contextlib
import importlib.util
import io
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("web_admin",ROOT/"src"/"open-web-gaming-admin.py")
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
SOURCE=(ROOT/"src"/"main.c").read_text()


class WebGamingAdminTests(unittest.TestCase):
    def execute(self, run_result=0, stderr="", tcp_ok=True, existing=False):
        output=io.StringIO()
        calls=[]
        responses=[subprocess.CompletedProcess([],0 if existing else 255,"",""),
                   subprocess.CompletedProcess([],run_result,"",stderr)]
        def fake_run(argv, seconds):
            calls.append(argv)
            return responses.pop(0)
        class Socket:
            def __enter__(self):return self
            def __exit__(self,*args):return False
        def connect(*args, **kwargs):
            if not tcp_ok:raise ConnectionRefusedError("test fixture")
            return Socket()
        with tempfile.TemporaryDirectory() as tmp:
            with (mock.patch.object(mod, "checked_run", side_effect=fake_run),
                  mock.patch.object(mod.shutil,"which", return_value="/usr/bin/ssh"),
                  mock.patch.object(mod.socket,"create_connection", side_effect=connect),
                  mock.patch.object(mod.subprocess,"Popen",side_effect=AssertionError("Python must not launch browser")),
                  contextlib.redirect_stdout(output)):
                rc=mod.open_admin("100.101.32.10","owner",Path(tmp))
        return rc,output.getvalue().strip(),calls

    def test_new_admin_tunnel_handoff_is_not_page_loaded(self):
        rc,status,calls=self.execute()
        self.assertEqual(rc,0)
        self.assertTrue(status.startswith("NOW_ADMIN_STATUS=tunnel_ready:"))
        port=int(status.rsplit(":",1)[1])
        self.assertGreaterEqual(port,20000)
        self.assertLess(port,40000)
        self.assertEqual(len(calls),2)
        self.assertIn("ExitOnForwardFailure=yes",calls[1])
        self.assertIn(f"127.0.0.1:{port}:127.0.0.1:8443",calls[1])

    def test_existing_master_reused_without_new_ssh(self):
        rc,status,calls=self.execute(existing=True)
        self.assertEqual(rc,0)
        self.assertEqual(len(calls),1)
        self.assertIn("tunnel_ready",status)

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
                rc,status,_=self.execute(run_result=255,stderr=stderr)
                self.assertEqual(rc,1)
                self.assertEqual(status,"NOW_ADMIN_STATUS="+kind)
                self.assertNotIn("publickey",status)

    def test_local_backend_listener_unreachable(self):
        rc,status,_=self.execute(tcp_ok=False)
        self.assertEqual(rc,1)
        self.assertEqual(status,"NOW_ADMIN_STATUS=admin_tunnel_unreachable")

    def test_invalid_settings_never_start_ssh(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=io.StringIO()
            with mock.patch.object(mod,"checked_run",side_effect=AssertionError("SSH launched")),contextlib.redirect_stdout(out):
                rc=mod.open_admin("host;bad","owner",Path(tmp))
            self.assertEqual(rc,2)
            self.assertEqual(out.getvalue().strip(),"NOW_ADMIN_STATUS=invalid_settings")

    def test_gui_launch_uses_gtk_and_validates_bounded_local_port(self):
        start=SOURCE.index("static void on_web_gaming_admin(void*w,void*p){")
        end=SOURCE.index("/* Open WebUI is",start)
        handler=SOURCE[start:end]
        self.assertIn("g_subprocess_communicate_utf8_async",handler)
        self.assertNotIn("now_launch(args)",handler)
        self.assertNotIn("OPENING WEB GAMING ADMIN VIA SSH",handler)
        self.assertIn("web_admin_finished",SOURCE)
        self.assertIn("g_subprocess_get_successful",SOURCE)
        self.assertIn("gtk_show_uri_on_window",SOURCE)
        self.assertIn("port>=20000 && port<40000",SOURCE)
        self.assertIn('"https://127.0.0.1:%ld/admin"',SOURCE)
        self.assertIn("ssh_not_authorized",SOURCE)
        self.assertIn("browser_error",SOURCE)

    def test_regular_web_gaming_pairing_does_not_use_ssh_admin(self):
        self.assertIn('button("PAIR WEB GAMING IN BROWSER","setupaction")',SOURCE)
        self.assertIn('wizard_button(c,four,"PAIR WEB GAMING IN BROWSER","w_webgaming")',SOURCE)
        self.assertIn('browser_open("https://games.monumentrisk.com");',SOURCE)
        self.assertIn("ENTER THE ACCESS PIN FROM THE SERVER OWNER",SOURCE)
        section=SOURCE[SOURCE.index('else if(resp==106){'):
                       SOURCE.index('else if(resp==104){')]
        self.assertNotIn("open-web-gaming-admin",section)
        self.assertNotIn("terminal_launch(",section)
        self.assertNotIn("ssh",section)

    def test_preserves_ssh_tunnel_tls_and_no_private_info(self):
        source=(ROOT/"src"/"open-web-gaming-admin.py").read_text()
        self.assertNotIn("verify=False",source)
        self.assertNotIn("--ignore-certificate-errors",source)
        self.assertNotIn("StrictHostKeyChecking=no",source)
        self.assertNotIn("stderr.strip()",source)
        self.assertNotIn("subprocess.Popen(",source)
        self.assertIn('"BatchMode=yes"',source)
        self.assertIn('"StrictHostKeyChecking=accept-new"',source)

if __name__=="__main__":unittest.main()
