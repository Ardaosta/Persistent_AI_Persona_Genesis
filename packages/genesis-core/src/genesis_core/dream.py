"""Daykey-gated inward reflection cycle.

The dream runs at most once per calendar day (enforced by the daykey ledger).
It gives the agent a quiet turn — no user present — to review memory, save
new insights, and write a brief journal entry.  The result is written to
vault/journal/YYYY-MM-DD.md so the agent can recall it in future sessions.

Daemon wiring (macOS): `genesis setup-daemon` generates the launchd plist
that calls `genesis dream` hourly; the daykey ensures actual work only once.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path


# ---------------------------------------------------------------------------
# Daykey ledger
# ---------------------------------------------------------------------------

def today_key() -> str:
    return date.today().isoformat()


def get_last_dream(root: Path) -> tuple[str, str] | None:
    """Return (iso-date, iso-datetime) of the most recent dream, or None."""
    ledger = root / "daykeys"
    if not ledger.exists():
        return None
    keys = sorted(ledger.glob("*.txt"), reverse=True)
    if not keys:
        return None
    day = keys[0].stem  # YYYY-MM-DD
    ts = keys[0].read_text(encoding="utf-8").strip()
    return day, ts


def already_dreamed_today(root: Path) -> bool:
    result = get_last_dream(root)
    return result is not None and result[0] == today_key()


def mark_dream(root: Path) -> str:
    """Write today's daykey and return the timestamp."""
    ts = datetime.now().isoformat()
    ledger = root / "daykeys"
    ledger.mkdir(parents=True, exist_ok=True)
    (ledger / f"{today_key()}.txt").write_text(ts, encoding="utf-8")
    return ts


# ---------------------------------------------------------------------------
# Journal
# ---------------------------------------------------------------------------

def write_journal(journal_dir: Path, reflection: str) -> Path:
    """Write the dream reflection to vault/journal/YYYY-MM-DD.md."""
    journal_dir.mkdir(parents=True, exist_ok=True)
    entry_path = journal_dir / f"{today_key()}.md"
    now = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    entry_path.write_text(f"# Dream — {now}\n\n{reflection.strip()}\n", encoding="utf-8")
    return entry_path


# ---------------------------------------------------------------------------
# Daemon helpers — moved to scheduler.py (cross-platform). Re-exported here for
# back-compat: `generate_wrapper`/`generate_plist` keep their old signatures.
# ---------------------------------------------------------------------------

from .scheduler import generate_plist, generate_wrapper  # noqa: E402,F401
