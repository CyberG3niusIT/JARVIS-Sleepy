"""Safety boundaries for the optional Mailcow integration (no network access)."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.mail_integration import SEND_ACCOUNTS, MailDenied, MailService


class _AllowGate:
    def assert_allowed(self, _capability):
        return None


class _ReadIMAP:
    def __init__(self, uids):
        self.uids = uids
        self.selected_readonly = []
        self.fetches = []

    def select(self, _folder, readonly=False):
        self.selected_readonly.append(readonly)
        return "OK", [b"1"]

    def response(self, _name):
        return "UIDVALIDITY", [b"9"]

    def myrights(self, _folder):
        return "OK", [b"INBOX lr"]

    def uid(self, command, *args):
        if command == "SEARCH":
            return "OK", [b" ".join(str(uid).encode() for uid in self.uids)]
        self.fetches.append(args)
        return "OK", [(b"header", b"From: sender@example.org\r\nSubject: Test\r\nMessage-ID: <test-2@example.org>\r\n\r\n")]

    def logout(self):
        return "BYE", [b""]


class MailIntegrationSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        path = Path(self.temp.name) / "config.json"
        path.write_text(json.dumps({"mailcow_address": "127.0.0.1",
                                    "reader": {"username": "reader", "password": "unused"},
                                    "writers": {"alex@wiesenmaier.org": {"password": "unused"},
                                                "info@wima-edv.de": {"password": "unused"}},
                                    "smtp": {"alex@wiesenmaier.org": "unused"}}))
        path.chmod(0o600)
        gate = patch("core.mail_integration.get_privacy_gate", return_value=_AllowGate())
        gate.start()
        self.addCleanup(gate.stop)
        self.service = MailService(path)

    def test_status_names_writable_accounts_from_backend_policy(self):
        with patch.object(self.service, "accounts", return_value=["alex@wiesenmaier.org"]), \
                patch.object(self.service, "unread", return_value=3):
            status = self.service.all_status()
        self.assertEqual(status["writable_accounts"], sorted(SEND_ACCOUNTS))
        self.assertEqual(status["accounts"], [{"account": "alex@wiesenmaier.org", "unread_inbox": 3, "new_24h": 0}])

    def test_unauthenticated_dashboard_shell_has_no_mailbox_identifiers(self):
        web = Path(__file__).resolve().parents[2] / "web"
        for name in ("dashboard_mail.html", "dashboard_mail.js"):
            text = (web / name).read_text(encoding="utf-8").lower()
            for account in SEND_ACCOUNTS:
                self.assertNotIn(account, text, name)
                self.assertNotIn(account.split("@", 1)[1], text, name)

    def test_only_two_senders_and_reply_source_is_verified(self):
        with self.assertRaises(MailDenied):
            self.service.create_draft({"from": "support@wima-edv.de", "to": ["a@example.org"]})
        with self.assertRaises(MailDenied):
            self.service.create_draft({"from": "alex@wiesenmaier.org", "to": ["a@example.org"],
                                       "reply_to_message": {"account": "info@wima-edv.de", "uid": 1}})
        with patch.object(self.service, "message", return_value={"message_id": "<real@example.org>"}):
            with self.assertRaises(MailDenied):
                self.service.create_draft({"from": "alex@wiesenmaier.org", "to": ["a@example.org"],
                                           "reply_to_message": {"account": "alex@wiesenmaier.org",
                                                                "uid": 1, "message_id": "<fake@example.org>"}})

    def test_writer_uses_only_its_own_mailbox_credential(self):
        with patch("core.mail_integration._PrivateIMAP") as imap:
            imap.return_value.login.return_value = ("OK", [b""])
            self.service._imap("alex@wiesenmaier.org", write=True)
            imap.return_value.login.assert_called_with("alex@wiesenmaier.org", "unused")
            with self.assertRaises(MailDenied):
                self.service._imap("support@wima-edv.de", write=True)
            self.assertEqual(imap.call_count, 1)

    def test_reader_refuses_master_owner_rights(self):
        client = _ReadIMAP([1])
        client.myrights = lambda _folder: ("OK", [b"INBOX lrswipkxte"])
        with patch.object(self.service, "_imap", return_value=client):
            with self.assertRaises(MailDenied):
                self.service.unread("alex@wiesenmaier.org")
        self.assertEqual(client.selected_readonly, [])

    def test_send_requires_exact_review_digest_and_is_one_shot(self):
        draft = self.service.create_draft({"from": "alex@wiesenmaier.org", "to": ["a@example.org"],
                                           "subject": "Test", "body": "Inhalt"})
        with patch("core.mail_integration.smtplib.SMTP") as smtp:
            with self.assertRaises(MailDenied):
                self.service.send_approved(draft["id"], "wrong")
            self.assertFalse(smtp.called)
            result = self.service.send_approved(draft["id"], draft["digest"])
            self.assertEqual(result["status"], "sent")
            with self.assertRaises(MailDenied):
                self.service.send_approved(draft["id"], draft["digest"])
            self.assertEqual(smtp.call_count, 1)

    def test_invalid_recipients_are_rejected_before_storage(self):
        for recipient in ("a@example.org\nBcc: bad@example.org", "not-an-address"):
            with self.subTest(recipient=recipient), self.assertRaises(MailDenied):
                self.service.create_draft({"from": "info@wima-edv.de", "to": [recipient]})

    def test_preview_selection_cannot_be_invented_or_replayed(self):
        with self.service._db() as db:
            db.execute("INSERT INTO previews VALUES(?,?,?,?,?,?,?)",
                       ("preview", "alex@wiesenmaier.org", "INBOX", "Rechtsanwalt",
                        json.dumps({"validity": "4", "items": [{"uid": 5, "sender": "a@example.org",
                                                                      "message_id": "<x>"}]}), "pending", 0))
        with self.assertRaises(MailDenied):
            self.service.approve_preview("preview", [6])
        with self.assertRaises(MailDenied):
            self.service.approve_preview("preview", [5, 5])

    def test_first_scan_is_baseline_and_later_mail_does_not_set_seen(self):
        client = _ReadIMAP([1])
        with patch.object(self.service, "accounts", return_value=["alex@wiesenmaier.org"]), \
             patch.object(self.service, "folders", return_value=["INBOX"]), \
             patch.object(self.service, "_imap", side_effect=lambda *_args, **_kwargs: client):
            self.assertEqual(self.service.poll_once(), {})
            client.uids = [1, 2]
            self.assertEqual(self.service.poll_once(), {"alex@wiesenmaier.org": 1})
        self.assertEqual(self.service.pending_notices()[0], {"alex@wiesenmaier.org": 1})
        self.assertEqual(self.service.suggestions()[0]["reason"], "unbekannter_absender")
        self.assertTrue(all(client.selected_readonly))
        self.assertTrue(all(b"BODY.PEEK" in str(fetch).encode() for fetch in client.fetches))

    def test_second_notification_cycle_does_not_repeat_after_ack(self):
        with self.service._db() as db:
            db.execute("INSERT INTO notices VALUES(?,?,?,?,?,?,0)",
                       ("n1", "info@wima-edv.de", "INBOX", "a@example.org", "Test", 0))
        counts, ids = self.service.pending_notices()
        self.assertEqual(counts, {"info@wima-edv.de": 1})
        self.service.mark_notified(ids)
        self.assertEqual(self.service.pending_notices(), ({}, []))


if __name__ == "__main__":
    unittest.main()
