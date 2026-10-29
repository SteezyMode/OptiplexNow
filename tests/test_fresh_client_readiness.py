"""Guard truthful first-run messaging and the separation of pairing and approval.

This is NOT a passing end-to-end QR enrollment or physical host test. It
prevents the wizard from implying that saving server coordinates grants access.
"""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
UI=(ROOT/"src/main.c").read_text()
CLIENT=(ROOT/"src/owner-enroll-client.py").read_text()
PACKAGE=(ROOT/"package.py").read_text()

class NewClientReadiness(unittest.TestCase):
    def test_server_selection_does_not_claim_authorization(self):
        self.assertIn('NEXT: VERIFY DEVICE ACCESS',UI)
        self.assertIn('Saving a server address does not pair Moonlight or authorize owner',UI)
        self.assertIn('APPROVE THIS DEVICE (OWNER QR)',UI)
        self.assertIn('SERVER LINUX ACCOUNT (OWNER ALPHA)',UI)
        self.assertNotIn('CONNECTION SETTINGS SAVED',UI)
        self.assertNotIn('Music is optional.',UI)

    def test_distinct_authorization_owners_remain_explicit(self):
        self.assertIn('Moonlight pairing authorizes Wolf-published streams only.',UI)
        self.assertIn("this alpha pairing path still needs trusted owner SSH",UI)
        self.assertIn('No administrator',UI)
        self.assertIn('credentials should be transferred to a new client.',UI)
        self.assertIn('approve_reviewed_tailnet(',CLIENT)
        self.assertIn('already_authorized(host, user)',CLIENT)
        self.assertIn('except ConnectionRefusedError:',CLIENT)

    def test_installer_does_not_install_or_enable_host_approval_service(self):
        self.assertIn("owner-enroll-ui.py", PACKAGE)
        self.assertIn("tailnet_enrollment.py", PACKAGE)
        self.assertIn("packaged but NEVER enabled by .deb", PACKAGE)
        self.assertNotIn("ssh-copy-id", CLIENT)

if __name__=="__main__":
    unittest.main()
