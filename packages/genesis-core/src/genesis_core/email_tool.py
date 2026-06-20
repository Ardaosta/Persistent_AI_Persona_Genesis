"""Email helpers for the Genesis AI.

Design (v0):
- email_draft: validates recipient against allowlist, checks daily cap,
  saves a draft JSON to root/email_queue/{id}.json, returns a formatted
  preview the agent can show the user.
- email_confirm: sends the saved draft via SMTP (STARTTLS), marks the
  daily ledger, moves the draft to email_sent/.

SMTP config lives in two secrets files:
  secrets/smtp.json  — {"host":..., "port":..., "user":..., "from_name":...}
  secrets/smtp.key   — the app password (plain text, mode 0600)

Daily cap: root/email_ledger/YYYY-MM-DD.json   {"count": N}
Draft queue: root/email_queue/{uuid}.json
Sent archive: root/email_sent/{uuid}.json
"""

from __future__ import annotations

import json
import smtplib
import uuid
from datetime import date, datetime
from email.mime.text import MIMEText
from pathlib import Path

from genesis_backend import ToolSpec

DAILY_CAP = 5

# ---------------------------------------------------------------------------
# Daily ledger
# ---------------------------------------------------------------------------

def _ledger_path(root: Path) -> Path:
    d = root / "email_ledger"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{date.today().isoformat()}.json"


def get_sent_today(root: Path) -> int:
    p = _ledger_path(root)
    if not p.exists():
        return 0
    return json.loads(p.read_text())["count"]


def _increment_sent(root: Path) -> int:
    p = _ledger_path(root)
    count = (json.loads(p.read_text())["count"] if p.exists() else 0) + 1
    p.write_text(json.dumps({"count": count}))
    return count


# ---------------------------------------------------------------------------
# Draft queue
# ---------------------------------------------------------------------------

def save_draft(root: Path, to: str, subject: str, body: str) -> str:
    draft_id = uuid.uuid4().hex[:12]
    q = root / "email_queue"
    q.mkdir(parents=True, exist_ok=True)
    draft = {
        "id": draft_id,
        "to": to,
        "subject": subject,
        "body": body,
        "created_at": datetime.now().isoformat(),
    }
    (q / f"{draft_id}.json").write_text(json.dumps(draft, indent=2))
    return draft_id


def load_draft(root: Path, draft_id: str) -> dict | None:
    p = root / "email_queue" / f"{draft_id}.json"
    if not p.exists():
        return None
    return json.loads(p.read_text())


def _archive_sent(root: Path, draft: dict) -> None:
    sent = root / "email_sent"
    sent.mkdir(parents=True, exist_ok=True)
    draft["sent_at"] = datetime.now().isoformat()
    (sent / f"{draft['id']}.json").write_text(json.dumps(draft, indent=2))
    queue_file = root / "email_queue" / f"{draft['id']}.json"
    if queue_file.exists():
        queue_file.unlink()


# ---------------------------------------------------------------------------
# SMTP
# ---------------------------------------------------------------------------

def _load_smtp_config(secrets_dir: Path) -> tuple[dict, str] | None:
    cfg_path = secrets_dir / "smtp.json"
    key_path = secrets_dir / "smtp.key"
    if not cfg_path.exists() or not key_path.exists():
        return None
    cfg = json.loads(cfg_path.read_text())
    key = key_path.read_text(encoding="utf-8").strip()
    return cfg, key


def send_via_smtp(secrets_dir: Path, draft: dict) -> str:
    """Send the draft; returns a status string. Raises on failure."""
    smtp_info = _load_smtp_config(secrets_dir)
    if smtp_info is None:
        return (
            "SMTP not configured — add secrets/smtp.json and secrets/smtp.key "
            "(see setup instructions)"
        )
    cfg, password = smtp_info
    from_addr = cfg["user"]
    from_name = cfg.get("from_name", "Genesis AI")

    msg = MIMEText(draft["body"], "plain", "utf-8")
    msg["Subject"] = draft["subject"]
    msg["To"] = draft["to"]
    msg["From"] = f"{from_name} <{from_addr}>"

    with smtplib.SMTP(cfg["host"], int(cfg.get("port", 587))) as s:
        s.ehlo()
        s.starttls()
        s.login(from_addr, password)
        s.sendmail(from_addr, [draft["to"]], msg.as_string())

    return f"sent to {draft['to']}"


# ---------------------------------------------------------------------------
# Tool implementations (return strings, never raise)
# ---------------------------------------------------------------------------

def tool_email_draft(
    to: str, subject: str, body: str,
    allowed_recipients: list[str], root: Path,
) -> str:
    if to not in allowed_recipients:
        return (
            f"denied: '{to}' is not on the allowed recipient list. "
            f"Allowed: {', '.join(allowed_recipients)}"
        )
    count = get_sent_today(root)
    if count >= DAILY_CAP:
        return f"denied: daily email cap ({DAILY_CAP}) reached for today"
    if not subject.strip():
        return "error: subject is required"
    if not body.strip():
        return "error: body is required"

    draft_id = save_draft(root, to, subject, body)
    preview = (
        f"Draft saved (id: {draft_id})\n\n"
        f"To:      {to}\n"
        f"Subject: {subject}\n\n"
        f"{body.strip()}\n\n"
        f"(Emails sent today: {count}/{DAILY_CAP})\n"
        f"Reply 'send it' or 'confirm' to send, or 'cancel' to discard."
    )
    return preview


def tool_email_confirm(draft_id: str, root: Path, secrets_dir: Path) -> str:
    draft = load_draft(root, draft_id)
    if draft is None:
        return f"error: no pending draft with id '{draft_id}'"
    try:
        status = send_via_smtp(secrets_dir, draft)
    except Exception as e:
        return f"send failed: {e}"
    _increment_sent(root)
    _archive_sent(root, draft)
    return status


# ---------------------------------------------------------------------------
# ToolSpec objects
# ---------------------------------------------------------------------------

EMAIL_DRAFT_TOOL = ToolSpec(
    name="email_draft",
    description=(
        "Compose an email draft to an allowed recipient and save it for review. "
        "Always show the full draft to the user before calling email_confirm. "
        "Summarize the ask in your own words — never paste raw vault contents."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "to": {"type": "string", "description": "recipient email address"},
            "subject": {"type": "string"},
            "body": {"type": "string", "description": "plain-text email body"},
        },
        "required": ["to", "subject", "body"],
    },
)

EMAIL_CONFIRM_TOOL = ToolSpec(
    name="email_confirm",
    description=(
        "Send a previously drafted email after the user has confirmed they want it sent. "
        "Never call this without explicit user approval."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "draft_id": {"type": "string", "description": "the id returned by email_draft"},
        },
        "required": ["draft_id"],
    },
)
