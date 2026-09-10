# genesis-headlines

Per-cluster **orientation that survives name-drift**, with a drift-proof resolver
and an engine-agnostic surfacing step. Framework machinery, content-free: a fresh
companion's `headlines/` dir is empty, and empty is the correct day-0 state.

Full design + host-integration guide: [`../../docs/HEADLINES.md`](../../docs/HEADLINES.md).

## Why

Each project a companion accumulates carries a few load-bearing "huge things" a
cold session must not overlook (what supersedes what, where the store moved, the
constraint that bites). Names drift and task-scoped prompts don't name the frame
they're about to violate, so ordinary recall misses them. HEADLINES matches on
**what a session is doing** (prompt text + cwd) and surfaces the frame **before
it acts**.

## The seam (how a host wires it)

> The host hands the surfacer a **signal** (prompt text + cwd) and a **session
> id**; it hands back a **block to inject**, or nothing.

```python
from genesis_headlines import surface
r = surface("fix the voice loop", session_id="sess-123")
if r.matched:
    inject(r.text)   # once per session per cluster; inert on an empty store
```

Engine-specific code lives only in the adapter (a Claude Code hook, a Node
per-turn call, etc.). The core has no dependency on any harness's hook shape.

## CLI

```
genesis-headlines new <slug> --alias A --path P   # scaffold a cluster
genesis-headlines list                            # clusters + alias/path counts
genesis-headlines resolve "<signal>" [--json]     # which clusters a signal touches
genesis-headlines surface --hook-json             # dedup'd block for a hook (reads JSON on stdin)
genesis-headlines check [--signal "<s>"]          # lint clusters; test a match
```

## Quickstart

```sh
cd packages/genesis-headlines
python3 -m pytest -q     # green = the resolver + surfacer + scaffold work
```

Zero dependencies, Python 3.9+. The cluster-doc format is shared byte-for-byte
with the aimee-core reference resolver — coordinate format changes with that
owner (see the design note).
