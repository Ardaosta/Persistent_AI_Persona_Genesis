"""Where cluster docs live, and how to enumerate them.

The store is a flat directory of `<cluster-slug>.md` files. It lives in the
companion's own home (user-owned hardware, never shared infra), a peer to the
memory vault rather than inside it — headlines are hand-curated orientation, not
auto-grown one-fact memory.

Resolution order (first hit wins):

  1. an explicit ``dir=`` argument (tests, tooling);
  2. ``$GENESIS_HEADLINES_DIR`` (a host that keeps headlines somewhere specific);
  3. ``$GENESIS_ROOT/headlines`` (the normal case; ``GENESIS_ROOT`` defaults to
     ``~/.genesis`` — the same home the owned surface and boot-context use).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional


def genesis_root() -> Path:
    env = os.environ.get("GENESIS_ROOT")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".genesis"


def headlines_dir(dir: Optional[str] = None) -> Path:
    if dir:
        return Path(dir).expanduser()
    env = os.environ.get("GENESIS_HEADLINES_DIR")
    if env:
        return Path(env).expanduser()
    return genesis_root() / "headlines"


def state_dir() -> Path:
    """Where per-session dedup sentinels live (under the companion's home)."""
    env = os.environ.get("GENESIS_STATE_DIR")
    if env:
        return Path(env).expanduser()
    return genesis_root() / "state"


def cluster_paths(dir: Optional[str] = None) -> List[Path]:
    """Every cluster doc, sorted. Empty (missing dir) is a valid day-0 state."""
    d = headlines_dir(dir)
    if not d.is_dir():
        return []
    return sorted(d.glob("*.md"))
