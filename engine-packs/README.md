# Genesis engine packs

The vault, memory, identity, and boot ritual are **always Genesis's** and **always on the user's own machine**. What an engine pack changes is *which agent loop drives them*.

## Two runtime modes

- **Mode A — Genesis's own loop** (`genesis-core`): native tool use over the seam, any engine, lightweight (Python only). Works everywhere; less capable than a mature agentic harness (no broad MCP ecosystem, no subagents/skills, deny-list not a real sandbox — see `DESIGN.md` and the capability gap analysis).
- **Mode B — a supported agentic *harness* wired to the vault** (these packs): the user runs a real agentic harness locally (Claude Code being the strongest), and Genesis configures **it** to use the Genesis vault/memory/boot-ritual. The muscle is the harness's (its tools, MCP, subagents, skills, sandbox, IDE); the soul/memory/identity is Genesis's; the data stays local; the engine is the user's own key. This is exactly how the reference companion runs. Far more capable; available only for engines we've mapped; carries that harness's footprint (Claude Code needs node + the CLI).

Mode B closes most of the Claude-Code capability gap for supported engines. It reframes Genesis as **the persistent-self layer that rides on top of whatever agentic harness you run**, not a reimplementation of one.

## What an engine pack is

Reference knowledge + content-free config templates that let the install agent wire a specific engine's harness into the Genesis stack:
- the **boot ritual** (load SOUL + lean index + recent continuity + live wall-clock before turn 1, harness-enforced),
- the single **blessed write path** + lean index,
- the **anti-drift disciplines** and the **boundary disposition**,

all content-free, so identity stays un-authored. Supported engines get the pack and the install agent auto-bootstraps them; any other engine still works via Mode A with manual setup.

## Recommendation: agentic engines only

Genesis runs on whatever LLM the user wants, but we **only recommend true agentic models** — ones that do reliable multi-step native tool use. A chat-only model can't be a capable Companion because it can't *act*. "Supported" = we ship a pack and auto-bootstrap; "any engine" = works via Mode A's seam, manual, no promises on agentic depth.

## Status

- `claude-code/` — **shipped**, grounded in the reference companion. Recommended. Modes A + B.
- `openai/`, `gemini/`, `grok/` — **research-needed stubs.** Each needs its agentic harness mapped (with a grounded research pass) before we claim Mode B support. Do not fabricate harness details.
