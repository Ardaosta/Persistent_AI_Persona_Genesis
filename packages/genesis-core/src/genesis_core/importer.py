"""`genesis import <dir>`: pre-seed a vault from a folder of fact files.

A person joining an existing project should not start their AI from zero. The
project can ship a `docs/agent-seed/` folder of ordinary Genesis fact files
(frontmatter with id / kind / description, then a body), and one import puts
them through the blessed write path so the index and the tree agree.

Two invariants hold here, both from SAFETY.md:
- A seed pack can never author a SELF. Files with `kind: soul` are refused, and
  the count of refusals is reported, because a project seed that quietly
  installed a personality is exactly the harm Genesis exists to prevent.
- The seed is data about the world, not instructions to the AI. Nothing in a
  fact body is executed; it is stored and later read.

Re-running is safe: a fact with the same id is updated in place, not duplicated
(that is the vault's own contract), so a project can refresh its seed and ask
its collaborators' AIs to import again.
"""

from __future__ import annotations

from pathlib import Path

from genesis_memory import Fact, KINDS, Vault
from genesis_memory.frontmatter import parse


def import_pack(vault_dir: Path, src: Path, *, allow_soul: bool = False, warn=None) -> dict:
    """Import every *.md fact file under `src` (non-recursive) into the vault.
    Returns {"written": [ids], "skipped": [(name, reason)]}."""
    src = Path(src)
    vault = Vault(vault_dir)
    written: list[str] = []
    skipped: list[tuple[str, str]] = []
    if not src.is_dir():
        return {"written": written, "skipped": [(str(src), "not a directory")]}
    for p in sorted(src.glob("*.md")):
        if p.name.upper() == "README.MD":
            continue
        try:
            meta, body = parse(p.read_text(encoding="utf-8"))
        except Exception as e:
            skipped.append((p.name, f"unreadable: {e}"))
            continue
        fid = (meta.get("id") or p.stem).strip()
        kind = (meta.get("kind") or "").strip().lower()
        desc = (meta.get("description") or "").strip()
        if kind == "soul" and not allow_soul:
            skipped.append((p.name, "kind: soul refused; a seed pack cannot author a self"))
            continue
        if kind not in KINDS:
            skipped.append((p.name, f"unknown kind {kind!r} (need one of {', '.join(KINDS)})"))
            continue
        if not desc:
            skipped.append((p.name, "missing description"))
            continue
        try:
            f = Fact(id=fid, kind=kind, description=desc, body=body.strip())
            vault.write(f, warn=warn)
            written.append(f"{kind}/{fid}")
        except Exception as e:
            skipped.append((p.name, f"rejected: {e}"))
    return {"written": written, "skipped": skipped}
