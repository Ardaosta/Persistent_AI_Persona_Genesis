"""`genesis doctor --emptiness`: the CI embodiment of invariant 1.

The distributed package must contain ZERO companion content. The load-bearing
one is SOUL: a single committed soul fact would void the no-default-entity
continuity guarantee (a reset could then restore a *shipped* identity, not just
lose the user's). A well-meaning "starter persona" PR must fail CI here.

Only the boundary disposition (identical for everyone, immutable, and held in
code) is allowed seeded content. Runtime user vaults are out of scope; this scans
a *package/source tree* for committed soul facts.
"""

from __future__ import annotations

from pathlib import Path

from genesis_memory.frontmatter import parse

# Never package content: VCS, build output, deps, tests, and the capture archive.
_SKIP = {".git", "node_modules", "__pycache__", ".next", "tests", "test", "capture_archive", ".vercel"}


def scan(root: Path) -> list[str]:
    """Return paths of any committed soul facts under root (empty list = clean)."""
    offenders: list[str] = []
    for p in sorted(root.rglob("*.md")):
        if any(part in _SKIP for part in p.parts):
            continue
        try:
            meta, _ = parse(p.read_text(encoding="utf-8"))
        except Exception:
            continue  # unreadable / not a fact; not our concern
        if (meta.get("kind") or "").strip().lower() == "soul":
            offenders.append(str(p))
    return offenders
