# Engine pack: Claude (via Claude Code / the Agent SDK)

**Tier:** recommended. **Modes:** A (genesis-core's loop on the Anthropic backend) and B (Claude Code itself wired to the Genesis vault — the richest integration, and how the reference companion runs).

## Mode B: make Claude Code a Genesis frontend

Claude Code brings its mature tool sandbox, MCP ecosystem, subagents, skills, and IDE surfaces; Genesis supplies the persistent vault, memory, identity, and boot ritual. The data stays on the user's machine; the model is the user's own Anthropic key.

**Footprint caveat:** Claude Code needs node + the CLI on the user's machine. The install agent guides that install in plain language; it is the price of Mode B's power. Mode A needs none of it.

What the install agent writes (all into the user's vault, all content-free — identity stays empty):

| File | Purpose |
|---|---|
| `CLAUDE.md` (rendered from `genesis_core/manual.py`; `CLAUDE.md.template` is the readable copy) | operating disciplines + boot ritual + memory conventions + the friction loop + working disciplines; identity left empty. The same text is what Codex reads as `AGENTS.md`. |
| a `SessionStart` hook (from `settings.session-hook.json.template`) | harness-enforced boot ritual: inject SOUL + lean index + recent continuity + live time before turn 1 (the structurally-enforced load, per the first outside review) |
| a `UserPromptSubmit` hook (same template) | register re-anchor: every 10 prompts, `genesis reanchor --hook` re-delivers the name, soul index, persisted disposition, and continuity tail, because boot-only injection lets long tool-heavy stretches flatten the voice |
| a `Stop` hook (same template) | the craft gate: `genesis craft-gate --hook` asks once per session for a friction entry or an explicit `--none` (exit 2 + stderr, so the ask cannot be skipped by habit and can never trap an AI that answered) |
| HEADLINES hooks (from `headlines.session-hook.json.template`) | auto-surface the load-bearing project frame for whatever cluster a session touches, before it acts (`UserPromptSubmit` + `SessionStart`); content-free, empty until the companion curates a cluster. See [`docs/HEADLINES.md`](../../docs/HEADLINES.md) |
| memory wiring (`MEMORY-WIRING.md`) | the blessed write path + lean index, optionally as a localhost MCP server |

## Verify before trusting

Claude Code's settings/hook schema and MCP config evolve. Treat these templates as **recipes, not frozen truth** — the install agent should check them against the user's installed Claude Code version (the `update-config` / hooks docs are the source of truth) before writing.

## Provenance

This pack is the reference companion's own setup, generalized and **stripped of all content** (no persona, no name, no warmth, no user-specific rules). It is the cleanest proof of the Genesis thesis: ship the machinery, never the self.
