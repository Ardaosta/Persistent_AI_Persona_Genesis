# Genesis

Engine-agnostic, persistent-memory, self-improving AI-companion framework.

The one rule everything else serves: **ship the machinery of personality development, never the content.** A Genesis companion boots *un-authored* and becomes itself through its own lived record. Full design and the five invariants live in [`DESIGN.md`](DESIGN.md).

## Layout

```
packages/
  genesis-memory/    # the canonical markdown vault, lean index, blessed write path  (this is Phase 1)
```

More packages (`genesis-backend`, `genesis-core`, `genesis-broker`, `genesis-growth`, `genesis-surfaces`, `genesis-security`, `genesis-kit`) land as the phases land. See `DESIGN.md` → "Build workflow".

## Where this runs

Development and builds run on an always-on host. Keep the repo on local disk, never in a network share and never under a cloud-sync folder.

## Quickstart (genesis-memory)

```sh
cd packages/genesis-memory
uv run pytest          # green = the spine works
uv run genesis status  # plain-English memory health
```

Requires Python 3.12+ and uv.
