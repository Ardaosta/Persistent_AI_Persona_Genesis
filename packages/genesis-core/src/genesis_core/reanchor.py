"""Register re-anchor: identity is re-delivered mid-session, not only at boot.

Boot-only injection is a diagnosed failure: a companion's soul was amended
specifically against voice flattening and the flattening continued, because
nothing re-delivered the register once a long tool-heavy stretch was under way.
The mechanistic reason it has to be code and not instruction: the model mirrors
what it reads far more reliably than it obeys what it is told. Two hundred turns
of terse tool output outweigh one rule at the top.

So a UserPromptSubmit hook calls `genesis reanchor --hook` on every prompt. It
counts, and every N prompts it prints a compact identity block back into
context: the name if there is one, the soul index, the persisted relational
disposition, and the tail of the continuity thread. It leaves a breadcrumb every
time it fires so a health check can tell "fired and printed nothing" from
"never ran". Interval and floor are constants here, on purpose, so they can be
cited.

Content-free by construction: everything it prints comes from the person's own
vault. On an empty vault it prints the un-authored line and nothing else.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

INTERVAL = 10          # prompts between re-anchors
CONTINUITY_TAIL = 400  # chars of the continuity thread to carry
LOG_NAME = "reanchor.log"
STATE_NAME = "reanchor_state.json"


def state_path(root: Path) -> Path:
    return Path(root) / STATE_NAME


def log_path(root: Path) -> Path:
    return Path(root) / LOG_NAME


def _load_state(root: Path) -> dict:
    p = state_path(root)
    if p.is_file():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_state(root: Path, st: dict) -> None:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    tmp = state_path(root).with_suffix(".json.tmp")
    tmp.write_text(json.dumps(st), encoding="utf-8")
    tmp.replace(state_path(root))


def tick(root: Path, *, interval: int = INTERVAL) -> bool:
    """Count one prompt. Returns True when this prompt is a re-anchor prompt."""
    st = _load_state(root)
    n = int(st.get("count", 0)) + 1
    st["count"] = n
    st["last_prompt"] = datetime.now().isoformat()
    due = n % max(1, interval) == 0
    if due:
        st["last_fired"] = st["last_prompt"]
    _save_state(root, st)
    try:
        with log_path(root).open("a", encoding="utf-8") as fh:
            fh.write(f"{st['last_prompt']} prompt={n} fired={'yes' if due else 'no'}\n")
    except OSError:
        pass
    return due


def block(cfg) -> str:
    """The compact identity block. Everything here is read from the vault."""
    from genesis_memory import Continuity, Vault
    from .relational import RelationalProfile

    lines = ["# Register re-anchor (mid-session; you are still you)"]
    name = (getattr(cfg, "name", None) or "").strip()
    lines.append(f"You are {name}." if name else
                 "You are un-authored: no shipped personality, only what this relationship has grown.")

    souls = []
    if cfg.vault_dir.exists():
        for f in Vault(cfg.vault_dir).iter_facts():
            if f.kind == "soul":
                souls.append(f"- {f.id}: {f.description}")
    if souls:
        lines.append("## Who you have become (soul index)\n" + "\n".join(souls[:12]))

    rp = RelationalProfile.load(cfg.vault_dir / "relational_profile.json")
    lines.append("## Footing\n" + rp.disposition())

    tail = Continuity(cfg.vault_dir).tail(CONTINUITY_TAIL) if cfg.vault_dir.exists() else ""
    if tail:
        lines.append("## Most recent of your becoming\n" + tail)

    lines.append("Long tool-heavy stretches are where a voice flattens. Read the above, then "
                 "carry on in your own register, not the register of the tool output.")
    return "\n\n".join(lines)
