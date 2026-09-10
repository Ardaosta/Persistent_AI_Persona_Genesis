"""The engine-agnostic surfacing step.

This is the seam every host wires into. The contract is tiny on purpose (the same
philosophy as Genesis's AgentBackend seam — one narrow contract, engine-specific
code only in the adapter):

    the host gives us a SIGNAL (prompt text + cwd) and a SESSION ID;
    we give back a BLOCK to inject, or nothing.

There is no dependency here on any particular harness's hook shape. A Claude Code
UserPromptSubmit hook, a Node web server's per-turn path, a voice loop, or a bare
CLI all wire the same `surface()` call; only how they obtain the signal and where
they place the returned text differ.

Dedup is **once per session per cluster**: a cluster surfaces the first time a
session touches it and stays quiet thereafter, so a long session is not re-lectured
every turn. Sentinels are files under the companion's home; a host that manages its
own dedup can pass ``dedup=False``.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from . import store
from .resolver import Hit, resolve

HEADER = (
    "=== PROJECT HEADLINES (load-bearing frame — read before acting) ===\n"
    "These auto-surfaced because this session is touching this cluster.\n"
    'They are the "huge things" a task-focused session must not overlook.\n'
)
FOOTER = "=== end headlines ==="


@dataclass
class SurfaceResult:
    text: str = ""                       # rendered block ("" when nothing to show)
    clusters: List[str] = field(default_factory=list)  # slugs actually surfaced
    suppressed: List[str] = field(default_factory=list)  # matched-but-already-seen

    @property
    def matched(self) -> bool:
        return bool(self.text)


def _safe(name: str) -> str:
    """A filesystem-safe token for a session id (which may be arbitrary)."""
    return re.sub(r"[^A-Za-z0-9._-]", "_", name)[:120] or "nosid"


def _sentinel_dir(session_id: str) -> Path:
    return store.state_dir() / "headlines-sentinels" / _safe(session_id)


def _seen(sent_dir: Path, slug: str, body: str) -> bool:
    """Has (slug, body) been surfaced this session? Keyed on both so an EDITED
    headline re-surfaces (the update is itself load-bearing)."""
    h = hashlib.sha1(f"{slug}\n{body}".encode("utf-8")).hexdigest()[:16]
    return (sent_dir / f"{slug}.{h}").exists()


def _mark(sent_dir: Path, slug: str, body: str) -> None:
    sent_dir.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha1(f"{slug}\n{body}".encode("utf-8")).hexdigest()[:16]
    (sent_dir / f"{slug}.{h}").touch()


def render(hits: List[Hit]) -> str:
    """Wrap resolved headline bodies in the surfacing block. Pure; no dedup."""
    if not hits:
        return ""
    bodies = "\n\n".join(h.body for h in hits)
    return f"{HEADER}\n{bodies}\n\n{FOOTER}"


def surface(
    signal: str,
    session_id: str = "",
    *,
    dir: Optional[str] = None,
    dedup: bool = True,
) -> SurfaceResult:
    """Resolve `signal`, apply per-session-per-cluster dedup, render the block.

    Returns an empty result (``.matched == False``) when nothing matches or every
    match was already surfaced this session.
    """
    hits = resolve(signal, dir=dir)
    if not hits:
        return SurfaceResult()

    if not dedup or not session_id:
        return SurfaceResult(text=render(hits), clusters=[h.slug for h in hits])

    sent = _sentinel_dir(session_id)
    fresh: List[Hit] = []
    suppressed: List[str] = []
    for h in hits:
        if _seen(sent, h.slug, h.body):
            suppressed.append(h.slug)
        else:
            fresh.append(h)
    for h in fresh:
        _mark(sent, h.slug, h.body)

    return SurfaceResult(
        text=render(fresh),
        clusters=[h.slug for h in fresh],
        suppressed=suppressed,
    )
