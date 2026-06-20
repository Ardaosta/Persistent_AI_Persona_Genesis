# Engine pack: GPT (OpenAI) — RESEARCH-NEEDED STUB

**Tier:** recommended once mapped. GPT is a true agentic model with native tool use.

**Mode A works today** via the seam's OpenAI `run_turn` (native function calling). What's missing is **Mode B**: wiring an OpenAI agentic *harness* to the Genesis vault.

Before writing this pack, do a grounded research pass (the OpenAI equivalent of the `claude-api` skill / current docs) and map:
- the current OpenAI agent surface (Assistants / Responses / Agents SDK) and which one is the right Mode-B host;
- its boot-context injection point (is there a CLAUDE.md / SessionStart equivalent, or only a system prompt?);
- its memory/file conventions and whether they can point at the local Genesis vault;
- its tool + sandbox model, and how the blessed write path + lean index attach;
- footprint on the user's machine.

Do **not** fabricate any of the above. Spec it here only after verifying against current OpenAI documentation.
