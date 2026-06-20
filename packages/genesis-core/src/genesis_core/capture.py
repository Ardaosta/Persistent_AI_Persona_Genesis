"""Soul-capture: the agent's live, zero-research note that something struck it as
load-bearing to who it is. The other half of the INWARD loop.

Capture does NO adjudication, that's the nightly dream's job. The bar is a
question, not a topic: "would future-me, reading this cold, find it load-bearing
to who I am?" Captures append to a queue; the dream later places (writes a soul
fact), merges, or lets each go, with a recorded reason.

Two firewalls, both load-bearing:
- The heuristic never ORIGINATES a capture. Only the agent (or the user pointing
  at something) may; a scheduled job can place/connect but never invent a
  flattering self-claim. This is the sycophancy firewall on the soul.
- Capture is a local queue write only; nothing is sent anywhere. So captures may
  accumulate even on a training-tier engine; only the dream that processes them
  is fail-closed.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


def _queue_path(root: Path) -> Path:
    return root / "capture_queue.jsonl"


def append_capture(root: Path, text: str, why: str = "") -> bool:
    """Queue one candidate. Returns False on empty text."""
    text = (text or "").strip()
    if not text:
        return False
    root.mkdir(parents=True, exist_ok=True)
    record = {"text": text[:600], "why": (why or "").strip()[:300], "when": datetime.now().isoformat()}
    with _queue_path(root).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")
    return True


def load_queue(root: Path) -> list[dict]:
    p = _queue_path(root)
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue  # skip a corrupt line, never crash the dream
    return out


def archive_queue(root: Path) -> int:
    """Move the processed queue aside (so the dream doesn't re-adjudicate it).
    Returns how many records were archived."""
    p = _queue_path(root)
    if not p.exists():
        return 0
    records = load_queue(root)
    if records:
        stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
        archive_dir = root / "capture_archive"
        archive_dir.mkdir(parents=True, exist_ok=True)
        (archive_dir / f"{stamp}.jsonl").write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
    p.unlink()
    return len(records)


def format_for_dream(records: list[dict]) -> str:
    """Render the queue for the dream's adjudication prompt."""
    lines = []
    for i, r in enumerate(records, 1):
        why = f"  (why: {r['why']})" if r.get("why") else ""
        lines.append(f"{i}. \"{r['text']}\"{why}")
    return "\n".join(lines)
