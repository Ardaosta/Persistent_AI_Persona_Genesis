# Engine pack: Claude (via Claude Code / the Agent SDK)

**Tier:** recommended. **Modes:** A (genesis-core's loop on the Anthropic backend) and B (Claude Code itself wired to the Genesis vault — the richest integration, and how the reference companion runs).

## Mode B: make Claude Code a Genesis frontend

Claude Code brings its mature tool sandbox, MCP ecosystem, subagents, skills, and IDE surfaces; Genesis supplies the persistent vault, memory, identity, and boot ritual. The data stays on the user's machine; the model is the user's own Anthropic key.

**Footprint caveat:** Claude Code needs node + the CLI on the user's machine. The install agent guides that install in plain language; it is the price of Mode B's power. Mode A needs none of it.

What the install agent writes (all into the user's vault, all content-free — identity stays empty):

| File | Purpose |
|---|---|
| `CLAUDE.md` (from `CLAUDE.md.template`) | operating disciplines + boot ritual + memory conventions; identity left empty |
| a `SessionStart` hook (from `settings.session-hook.json.template`) | harness-enforced boot ritual: inject SOUL + lean index + recent continuity + live time before turn 1 (the structurally-enforced load) |
| memory wiring (`MEMORY-WIRING.md`) | the blessed write path + lean index, optionally as a localhost MCP server |

## Verify before trusting

Claude Code's settings/hook schema and MCP config evolve. Treat these templates as **recipes, not frozen truth** — the install agent should check them against the user's installed Claude Code version (the `update-config` / hooks docs are the source of truth) before writing.

## Provenance

This pack is the reference companion's own setup, generalized and **stripped of all content** (no persona, no name, no warmth, no user-specific rules). It is the cleanest proof of the Genesis thesis: ship the machinery, never the self.
