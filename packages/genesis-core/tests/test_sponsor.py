"""Sponsor help-line: send builds the right message, check appends + marks seen,
and missing config fails closed with a clean message (no crash)."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from genesis_core import config as cfgmod
from genesis_core import sponsor


def _cfg(root, sender="agent@gmail.com", recip=("sponsor@example.com",), pw="apppassword"):
    c = cfgmod.GenesisConfig(root=root, sponsor_sender=sender,
                             allowed_email_recipients=list(recip))
    if pw is not None:
        c.secrets_dir.mkdir(parents=True, exist_ok=True)
        (c.secrets_dir / "sponsor_app_password").write_text(pw)
    return c


class TestSend(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.root = Path(self._td.name)

    def tearDown(self):
        self._td.cleanup()

    def test_send_builds_message_and_sends(self):
        cfg = _cfg(self.root)
        sent = {}
        fake = mock.MagicMock()
        fake.send_message.side_effect = lambda msg: sent.update(
            {"to": msg["To"], "from": msg["From"], "reply": msg["Reply-To"], "subj": msg["Subject"]}
        )
        with mock.patch.object(sponsor.smtplib, "SMTP", return_value=fake):
            to = sponsor.send_to_sponsor(cfg, "stuck on BLE CRC", "the checksum doesn't validate")
        self.assertEqual(to, "sponsor@example.com")
        self.assertEqual(sent["to"], "sponsor@example.com")
        self.assertEqual(sent["from"], "agent@gmail.com")
        self.assertEqual(sent["reply"], "agent@gmail.com")  # reply lands where the agent reads
        fake.login.assert_called_once()

    def test_send_fails_closed_without_password(self):
        cfg = _cfg(self.root, pw=None)
        with self.assertRaises(sponsor.SponsorError):
            sponsor.send_to_sponsor(cfg, "s", "b")

    def test_send_fails_closed_without_sender(self):
        cfg = _cfg(self.root, sender="")
        with self.assertRaises(sponsor.SponsorError):
            sponsor.send_to_sponsor(cfg, "s", "b")


class TestCheck(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.root = Path(self._td.name)

    def tearDown(self):
        self._td.cleanup()

    def test_check_appends_and_marks_seen(self):
        cfg = _cfg(self.root)
        raw = (b"From: A Sponsor <sponsor@example.com>\r\nSubject: re: stuck\r\n\r\n"
               b"Try the MODBUS poly 0xA001.\r\n")
        fake = mock.MagicMock()
        fake.search.return_value = ("OK", [b"7"])
        fake.fetch.return_value = ("OK", [(b"7 (RFC822)", raw)])
        with mock.patch.object(sponsor.imaplib, "IMAP4_SSL", return_value=fake):
            n = sponsor.check_sponsor_mail(cfg)
        self.assertEqual(n, 1)
        inbox = sponsor.inbox_path(cfg).read_text()
        self.assertIn("Try the MODBUS poly 0xA001.", inbox)
        self.assertIn("sponsor@example.com", inbox)
        fake.store.assert_called_with(b"7", "+FLAGS", "\\Seen")

    def test_check_no_unseen_is_zero(self):
        cfg = _cfg(self.root)
        fake = mock.MagicMock()
        fake.search.return_value = ("OK", [b""])
        with mock.patch.object(sponsor.imaplib, "IMAP4_SSL", return_value=fake):
            n = sponsor.check_sponsor_mail(cfg)
        self.assertEqual(n, 0)
        self.assertFalse(sponsor.inbox_path(cfg).exists())


if __name__ == "__main__":
    unittest.main()
