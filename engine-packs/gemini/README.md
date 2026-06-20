# Engine pack: Gemini (Google) — RESEARCH-NEEDED STUB

**Tier:** recommended once mapped. Gemini offers native function calling / agentic tool use.

A seam **Mode A** backend (a `GeminiBackend` implementing `run_turn` over Gemini's native tool-calling API) is not yet built — add it alongside the Anthropic/OpenAI adapters. **Mode B** (wiring a Gemini agentic harness — e.g. the Gemini CLI / its agent runtime — to the Genesis vault) is unspecified.

Before writing this pack, research and map (grounded, not from memory): Gemini's current agentic runtime/CLI, its native tool-call wire format (for the Mode A adapter), its boot-context injection point, its memory/file conventions against a local vault, and its footprint. Do not fabricate.
