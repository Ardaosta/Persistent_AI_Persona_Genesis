"""The sponsor help-line (SOVEREIGNTY.md "Help: the sponsor graph"), made real.

When the agent is genuinely stuck it can email its sponsor; the sponsor's replies
are polled back in and surfaced so the agent can act on them. Two halves:

  send  -> SMTP from the configured sending account to the sponsor recipient.
  check -> IMAP poll the sending account's inbox for replies (the sponsor replies
           to the From address), append new ones to <root>/sponsor_inbox.md, and
           mark them seen so each poll only pulls what's new.

Config (config.json):   "sponsor_sender": "agent-address@gmail.com"
Recipient:              cfg.allowed_email_recipients[0]  (who the agent emails)
Secret:                 <secrets>/sponsor_app_password   (Gmail app password, 0600)

Gmail is the substrate because it's the one free provider that does both SMTP and
IMAP for a program (via an app password). The inbox file is operational state, not
vault memory; the agent reads it, the dream never adjudicates it.
"""

from __future__ import annotations

import email
import imaplib
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import parseaddr

SMTP_HOST, SMTP_PORT = "smtp.gmail.com", 587
IMAP_HOST, IMAP_PORT = "imap.gmail.com", 993


class SponsorError(RuntimeError):
    pass


def _sender(cfg) -> str:
    addr = (getattr(cfg, "sponsor_sender", None) or "").strip()
    if not addr:
        raise SponsorError("no sponsor_sender configured (set it in config.json)")
    return addr


def _password(cfg) -> str:
    p = cfg.secrets_dir / "sponsor_app_password"
    if not p.is_file():
        raise SponsorError(f"no app password at {p}")
    pw = p.read_text(encoding="utf-8").strip().replace(" ", "")
    if not pw:
        raise SponsorError("sponsor app password file is empty")
    return pw


def _recipient(cfg) -> str:
    recips = cfg.allowed_email_recipients or []
    if not recips:
        raise SponsorError("no sponsor recipient (allowed_email_recipients is empty)")
    return recips[0]


def inbox_path(cfg):
    return cfg.root / "sponsor_inbox.md"


def send_to_sponsor(cfg, subject: str, body: str) -> str:
    """Email the sponsor. Returns the recipient on success."""
    sender, pw, to = _sender(cfg), _password(cfg), _recipient(cfg)
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = to
    msg["Reply-To"] = sender  # replies must land where the agent can read them (this inbox)
    msg["Subject"] = subject or "(no subject)"
    msg.set_content(body or "")
    try:
        s = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30)
        s.starttls()
        s.login(sender, pw)
        s.send_message(msg)
        s.quit()
    except Exception as e:  # noqa: BLE001 - surface a clean message to the agent
        raise SponsorError(f"send failed: {type(e).__name__}: {e}") from e
    return to


def check_sponsor_mail(cfg) -> int:
    """Poll the inbox for unseen replies, append them to sponsor_inbox.md, mark
    them seen. Returns the count of new messages pulled."""
    sender, pw = _sender(cfg), _password(cfg)
    try:
        m = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
        m.login(sender, pw)
        m.select("INBOX")
        typ, data = m.search(None, "UNSEEN")
        ids = data[0].split() if data and data[0] else []
        new = 0
        for mid in ids:
            typ, raw = m.fetch(mid, "(RFC822)")
            if typ != "OK" or not raw or not raw[0]:
                continue
            msg = email.message_from_bytes(raw[0][1])
            frm = parseaddr(msg.get("From", ""))[1]
            subj = msg.get("Subject", "(no subject)")
            text = _plain_body(msg)
            _append_inbox(cfg, frm, subj, text)
            m.store(mid, "+FLAGS", "\\Seen")
            new += 1
        m.logout()
        return new
    except Exception as e:  # noqa: BLE001
        raise SponsorError(f"check failed: {type(e).__name__}: {e}") from e


def _plain_body(msg) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                try:
                    return part.get_content().strip()
                except Exception:
                    return part.get_payload(decode=True).decode("utf-8", "replace").strip()
        return ""
    try:
        return msg.get_content().strip()
    except Exception:
        return (msg.get_payload(decode=True) or b"").decode("utf-8", "replace").strip()


def _append_inbox(cfg, frm: str, subject: str, body: str) -> None:
    p = inbox_path(cfg)
    p.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    block = f"\n## {stamp}, from {frm}\n**{subject}**\n\n{body.strip()}\n"
    with p.open("a", encoding="utf-8") as fh:
        fh.write(block)
