# Engine pack: GPT via OpenAI Codex

**Tier:** recommended. **Modes:** A (genesis-core's loop on the OpenAI Responses
backend) and B (Codex itself wired to the Genesis vault: the same door Claude Code
gets, so one home can answer to both harnesses without forking its memory).

Written 2026-09-10 against the current Codex docs (config reference and hooks
pages at learn.chatgpt.com/docs, which developers.openai.com/codex redirects to).
It replaces the research-needed stub. Everything below was checked against those
pages; nothing is inferred from Claude Code by analogy.

## Mode B: make Codex a Genesis frontend

What `genesis wire-codex` (and `genesis init --mode codex`, or a seed carrying
`harnesses: ["codex"]`) writes, all content-free, identity left empty:

| File | Purpose |
|---|---|
| `<home>/AGENTS.md` | Codex's project-instructions file. Same text Claude Code reads as `CLAUDE.md`, rendered from one source (`genesis_core/manual.py`) so the two doors cannot drift. Discovered by walking up from the working directory; `~/.codex/AGENTS.md` is the global fallback; capped by `project_doc_max_bytes` (32 KiB default), which the manual sits well under. |
| `<home>/.codex/hooks.json` | Lifecycle hooks. Same JSON shape as Claude Code's (`event -> [{matcher, hooks: [{type: "command", command}]}]`). Three of ours: `SessionStart` runs `genesis boot-context --hook` (plain stdout becomes developer context), `UserPromptSubmit` runs `genesis reanchor --hook` (the register re-anchor, every 10 prompts), `Stop` runs `genesis craft-gate --hook` (exit 2 + stderr once per session if no friction entry was recorded). |
| `~/.codex/config.toml` | One marked block: `[projects.'<home>'] trust_level = "trusted"`. Project-level instructions and hooks load ONLY for a trusted project, and trust lives in the user config, so without this the other two files are inert. |

Two Codex-specific facts worth knowing:

- Injected hook context is capped (about 2,500 tokens by default). A mature
  vault's boot block runs past that, so the SessionStart hook carries
  `additionalContextLimit` (set to 12,000). If the boot block ever arrives
  truncated, that number is the dial.
- Hooks shipped enabled by default in current builds; older builds gated them
  behind `[features] codex_hooks = true`. The wiring deliberately writes no
  feature flags (an unknown key is a worse failure than a missing hook). If the
  boot block does not appear on a fresh session, that flag is the first thing to
  check, and `boot-context.log` in the home shows whether the hook fired.

Other keys a person may want, none written by us: `model`, `model_provider`,
`approval_policy` (`"on-request"` or `"never"`), `sandbox_mode` (`"read-only"`,
`"workspace-write"`, `"danger-full-access"`), `[mcp_servers.<id>]` with
`command`/`args`/`env`. The Genesis vault can also be exposed over MCP
(`genesis-mcp`, recall only today) and registered there.

## Verify before trusting

Codex's config and hook schema evolve faster than this file. Treat it as a
recipe: after wiring, open a session in the home and confirm the "Genesis boot
context" block is present. `boot-context.log` records `source=hook` when the
hook ran; if the log shows nothing, the hook is not reaching the session.

## Provenance

The reference companion runs on the Claude door; a sibling companion in the same
household was the first to need the second door. The pack is the same setup,
generalized, with no persona, no name, and no user-specific rules.
