# Wiring Claude Code to the Genesis vault

Goal: Claude Code reads and writes the **same** `genesis-memory` vault that
Mode A uses, so switching modes never forks the memory.

## Layout (on the user's machine, under `$GENESIS_ROOT`)

```
$GENESIS_ROOT/
  vault/          the memory (one fact per file + the lean index)   ← tools target HERE
  secrets/        engine key, mode 0600                              ← sibling of vault; never a tool allow-root
  bin/            genesis-boot-context, the blessed write path
```

## Two ways to give Claude Code access (pick by how much the user wants installed)

1. **File + CLAUDE.md (simplest).** The `CLAUDE.md` template tells Claude Code the
   vault lives at `$GENESIS_ROOT/vault`, that the SessionStart hook loads the
   index, and to write durable facts only through the blessed write path
   (`$GENESIS_ROOT/bin/genesis-remember`). Claude Code's own Read/Write/Edit tools
   touch the vault directly; the write path keeps the index consistent.

2. **`genesis-memory` MCP server (richer).** Run `genesis-memory` as a
   localhost-only MCP server exposing `remember` / `recall` (and later search over
   sqlite/FTS5). Register it in the same settings file. This gives Claude Code
   structured, audited memory access instead of raw file edits, and matches the
   Mode A tool surface exactly.

Either way: the vault is the single source of truth, secrets stay outside every
tool's allow-root, and a Mode A ↔ Mode B switch reads the same files.

> Verify the current Claude Code MCP-registration and settings schema before
> writing config — treat this as a recipe, not frozen truth.
