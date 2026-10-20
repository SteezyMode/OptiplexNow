"""Personal-use NOW owner and household auto approval regression tests.

No production Tailscale, Wolf, Caddy, email, or Docker calls.
"""
import http.client
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import threading
import unittest

SRC=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(SRC/"server"))
import now_pairing_broker as broker
import now_pairing_requests as requests
import now_pairing_trust as trusted
MAIN=(SRC/"src"/"main.c").read_text()


class HouseholdAutoApprovalTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        os.chmod(self.temp.name,0o700)
        self.owner=requests.PeerIdentity("nOwnerDevice","1042")
        self.wife=requests.PeerIdentity("nWifeDevice","2055")
        self.unknown=requests.PeerIdentity("nUnknownDevice","3077")
        self.peer=self.owner
        self.policy=trusted.HouseholdTrust(self.temp.name,"1042",default_auto_owner=True)
        self.queue=requests.PairingRequests()
        self.server=broker.PairingHTTPServer(
            ("127.0.0.1",0),broker.make_handler(self.queue,
                verify=lambda ip:self.peer,owner_user_id="1042",household=self.policy))
        self.thread=threading.Thread(target=self.server.serve_forever,
                                     kwargs={"poll_interval":0.01},daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp.cleanup()

    def api(self,method,path,body=None,headers=None):
        conn=http.client.HTTPConnection("127.0.0.1",self.server.server_port,timeout=3)
        try:
            h={"X-NOW-Owner-Client":"desktop-v1"}
            if headers:h.update(headers)
            payload=None
            if body is not None:
                payload=json.dumps(body).encode()
                h["Content-Type"]="application/json"
            if method=="POST" and payload is None:payload=b""
            conn.request(method,path,body=payload,headers=h)
            response=conn.getresponse()
            return response.status,json.loads(response.read())
        finally:conn.close()

    def request(self):
        return self.api("POST",broker.REQUEST_ROUTE,{"backend":"wolf"})

    def test_owner_auto_approved_no_manual_inbox(self):
        code,response=self.request()
        self.assertEqual(code,202)
        self.assertEqual(response["owner_status"],"approved")
        self.assertFalse(response["moonlight_paired"])
        self.assertEqual(self.queue.owner_pending(),[])

    def test_unknown_and_family_not_preapproved(self):
        self.peer=self.wife
        _,result=self.request()
        self.assertEqual(result["owner_status"],"pending")
        self.peer=self.unknown
        _,result=self.request()
        self.assertEqual(result["owner_status"],"pending")

    def test_one_approval_marks_family_account_for_future_devices(self):
        self.peer=self.wife
        _,req=self.request()
        rid=req["request_id"]
        self.peer=self.owner
        code,result=self.api("POST",f"{broker.OWNER_LIST}/{rid}/approve-and-trust")
        self.assertEqual(code,200)
        self.assertTrue(result["future_devices_trusted"])
        self.assertFalse(result["moonlight_paired"])
        self.assertTrue(self.policy.trusts(self.wife))
        self.peer=requests.PeerIdentity("nWifeSecondLaptop","2055")
        _,second=self.request()
        self.assertEqual(second["owner_status"],"approved")
        self.assertFalse(second["moonlight_paired"])
        # Persisted policy survives a new broker instance.
        restored=trusted.HouseholdTrust(self.temp.name,"1042")
        self.assertTrue(restored.trusts(self.wife))
        self.assertEqual(restored.status()["trusted_family_count"],1)

    def test_owner_can_turn_auto_approval_off_and_on(self):
        path=broker.TRUST_SETTINGS
        self.peer=self.owner
        self.assertTrue(self.api("GET",path)[1]["auto_owner"])
        self.assertFalse(self.api("POST",path,{"auto_owner":False})[1]["auto_owner"])
        self.peer=requests.PeerIdentity("nOwnerDifferent","1042")
        self.assertEqual(self.request()[1]["owner_status"],"pending")
        self.peer=self.owner
        self.assertTrue(self.api("POST",path,{"auto_owner":True})[1]["auto_owner"])
        restored=trusted.HouseholdTrust(self.temp.name,"1042")
        self.assertTrue(restored.status()["auto_owner"])

    def test_wife_cannot_update_settings_or_trust_other_people(self):
        self.peer=self.unknown
        _,guest=self.request()
        rid=guest["request_id"]
        self.peer=self.wife
        self.assertEqual(self.api("GET",broker.TRUST_SETTINGS)[0],403)
        self.assertEqual(self.api("POST",broker.TRUST_SETTINGS,{"auto_owner":True})[0],403)
        self.assertEqual(self.api("POST",f"{broker.OWNER_LIST}/{rid}/approve-and-trust")[0],403)
        self.assertEqual(self.queue.status_for_peer(self.unknown,rid),"pending")

    def test_no_auto_approval_when_disabled_by_default(self):
        with tempfile.TemporaryDirectory() as folder:
            os.chmod(folder,0o700)
            policy=trusted.HouseholdTrust(folder,"1042")
            self.assertFalse(policy.trusts(self.owner))
            self.assertFalse(policy.trusts(self.wife))
            with self.assertRaises(PermissionError):
                trusted.HouseholdTrust(folder,"2055")

    def test_policy_permissions_and_gui_paths(self):
        path=Path(self.temp.name)/"household-trust.json"
        self.assertEqual(stat.S_IMODE(path.stat().st_mode),0o600)
        self.assertIn('HOUSEHOLD TAILSCALE AUTO-APPROVAL',MAIN)
        self.assertIn('"w_household"',MAIN)
        self.assertIn('APPROVE + TRUST ACCOUNT',MAIN)
        self.assertIn('choice==4?"trust"',MAIN)
        self.assertNotIn('terminal_launch(',MAIN[
            MAIN.index("static void on_household_settings("):
            MAIN.index("static void on_web_gaming_admin(")])

if __name__=="__main__":unittest.main()
