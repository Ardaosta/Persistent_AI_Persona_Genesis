"""Genesis HEADLINES — orientation that survives name-drift.

A companion accumulates projects. Each one carries a handful of load-bearing
"huge things" a cold, task-focused session must not overlook (what supersedes
what, where the canonical store moved, the constraint that bites if unknown).
Ordinary memory recall does not reliably surface those, because the names drift
(one system goes by five names over its life) and a task-scoped prompt rarely
names the frame it is about to violate.

HEADLINES fixes this with three content-free parts:

  * a **cluster store** — one curated markdown doc per system, carrying a fat
    `aliases` net + real `paths`, matched on WHAT A SESSION IS DOING rather than
    on any canonical name;
  * a **drift-proof resolver** — given a signal blob (prompt text + cwd), return
    the clusters that signal touches;
  * an **engine-agnostic surfacing step** — the host hands us a signal and a
    session id; we hand back a block to inject (once per session per cluster), or
    nothing.

Ship the machinery, never the content: a fresh companion's headlines dir is
empty, and empty is the correct day-0 state.
"""
from __future__ import annotations

__version__ = "0.0.1"

from .resolver import Hit, resolve  # noqa: E402
from .store import cluster_paths, headlines_dir  # noqa: E402
from .surface import surface  # noqa: E402

__all__ = ["Hit", "resolve", "surface", "headlines_dir", "cluster_paths", "__version__"]
