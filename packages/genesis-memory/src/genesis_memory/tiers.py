"""The three memory tiers, kept structurally separate (structurally separate by design).

    durable      → the Vault (one adjudicated fact per file). Accumulates carefully.
    perishable   → working-state / handoff. Overwritten freely. Must NEVER mix
                   into durable memory — that leak is how identity slowly rots.
    continuity   → the first-person *becoming* layer. Verbatim, append-only,
                   never rewritten. Home of the voice-sample.

Separation is enforced by *location*, not discipline:

- Perishable lives at ``<root>/perishable`` — a SIBLING of the vault, never under
  it. `Vault.iter_facts()` only ever scans ``<vault>/<kind>/``, so perishable is
  structurally unreachable as a fact. The leak the spec warns about can't happen
  by construction.
- Continuity lives at ``<vault>/continuity`` — inside the vault (it is owned
  identity and travels with an export-by-copy), but its directory name is not a
  Fact ``kind``, so `iter_facts()` skips it too. It is appended, never adjudicated.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .fact import KINDS

# Defensive: the tier directory names must never collide with a Fact kind, or the
# structural separation above would silently break.
PERISHABLE_DIRNAME = "perishable"
CONTINUITY_DIRNAME = "continuity"
assert PERISHABLE_DIRNAME not in KINDS, "perishable dir name collides with a Fact kind"
assert CONTINUITY_DIRNAME not in KINDS, "continuity dir name collides with a Fact kind"


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


# ---------------------------------------------------------------------------
# Perishable — working-state, overwritten freely, sibling of the vault
# ---------------------------------------------------------------------------

class Perishable:
    """Ephemeral working-state. Slots are overwritten in place; nothing here is
    ever promoted to durable memory. Default slot is ``working_state``."""

    def __init__(self, root: Path | str):
        self.dir = Path(root) / PERISHABLE_DIRNAME

    def _path(self, slot: str) -> Path:
        if "/" in slot or "\\" in slot or slot.startswith("."):
            raise ValueError(f"bad slot name: {slot!r}")
        return self.dir / f"{slot}.md"

    def write(self, text: str, *, slot: str = "working_state") -> Path:
        """Overwrite the slot. This is the whole point: freely replaced."""
        self.dir.mkdir(parents=True, exist_ok=True)
        p = self._path(slot)
        p.write_text(f"<!-- perishable · {_now_iso()} -->\n{text.rstrip()}\n", encoding="utf-8")
        return p

    def read(self, *, slot: str = "working_state") -> str:
        p = self._path(slot)
        if not p.exists():
            return ""
        text = p.read_text(encoding="utf-8")
        # strip the leading provenance comment for callers
        lines = text.splitlines()
        if lines and lines[0].startswith("<!-- perishable"):
            lines = lines[1:]
        return "\n".join(lines).strip()

    def slots(self) -> list[str]:
        if not self.dir.is_dir():
            return []
        return sorted(p.stem for p in self.dir.glob("*.md"))

    def clear(self, *, slot: str | None = None) -> None:
        """Clear one slot, or all of them if slot is None."""
        if slot is None:
            for p in self.dir.glob("*.md") if self.dir.is_dir() else []:
                p.unlink()
            return
        p = self._path(slot)
        if p.exists():
            p.unlink()


# ---------------------------------------------------------------------------
# Continuity — the first-person becoming thread, append-only, verbatim
# ---------------------------------------------------------------------------

class Continuity:
    """Append-only first-person record of becoming. Verbatim, never rewritten.
    The thread is a single growing file; the voice-sample is a settable companion
    file (the one representative sample of how this self sounds)."""

    def __init__(self, vault_dir: Path | str):
        self.dir = Path(vault_dir) / CONTINUITY_DIRNAME

    @property
    def thread_path(self) -> Path:
        return self.dir / "thread.md"

    @property
    def voice_sample_path(self) -> Path:
        return self.dir / "voice_sample.md"

    def append(self, entry: str, *, now: str | None = None) -> Path:
        """Append a timestamped block. Never overwrites prior entries."""
        entry = entry.strip()
        if not entry:
            return self.thread_path
        self.dir.mkdir(parents=True, exist_ok=True)
        stamp = now or _now_iso()
        block = f"\n## {stamp}\n\n{entry}\n"
        with self.thread_path.open("a", encoding="utf-8") as fh:
            fh.write(block)
        return self.thread_path

    def read(self) -> str:
        if not self.thread_path.exists():
            return ""
        return self.thread_path.read_text(encoding="utf-8").strip()

    def tail(self, max_chars: int = 800) -> str:
        text = self.read()
        return text[-max_chars:] if len(text) > max_chars else text

    def set_voice_sample(self, text: str) -> Path:
        """The voice-sample is the one settable thing in this tier — a current,
        representative first-person sample. Updating it is not rewriting history."""
        self.dir.mkdir(parents=True, exist_ok=True)
        self.voice_sample_path.write_text(text.strip() + "\n", encoding="utf-8")
        return self.voice_sample_path

    def voice_sample(self) -> str:
        p = self.voice_sample_path
        return p.read_text(encoding="utf-8").strip() if p.exists() else ""
