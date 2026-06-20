"""The vault: the canonical, owned, human-readable source of truth.

One fact per file at `<root>/<kind>/<id>.md`. Every durable write goes through
`Vault.write` (the single blessed write path), which stamps timestamps and
serializes via the tolerant frontmatter writer. Reads round-trip back to Facts.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from . import frontmatter
from .fact import KINDS, Fact

_KNOWN = {"id", "description", "kind", "status", "created", "updated", "_raw"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class Vault:
    def __init__(self, root: Path | str):
        self.root = Path(root)

    def path_for(self, fact: Fact) -> Path:
        return self.root / fact.kind / f"{fact.id}.md"

    def write(self, fact: Fact, *, now: str | None = None) -> Path:
        """The single blessed write path. `now` is injectable for deterministic tests."""
        stamp = now or _now_iso()
        if fact.created is None:
            fact.created = stamp
        fact.updated = stamp

        meta = {
            "id": fact.id,
            "description": " ".join(fact.description.split()),  # single-line at the write boundary
            "kind": fact.kind,
            "status": fact.status,
            "created": fact.created,
            "updated": fact.updated,
        }
        meta.update(fact.extra)

        path = self.path_for(fact)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(frontmatter.serialize(meta, fact.body), encoding="utf-8")
        return path

    def read(self, path: Path | str) -> Fact:
        path = Path(path)
        meta, body = frontmatter.parse(path.read_text(encoding="utf-8"))
        extra = {k: v for k, v in meta.items() if k not in _KNOWN}
        return Fact(
            id=meta.get("id", path.stem),
            kind=meta.get("kind", path.parent.name),
            description=meta.get("description", ""),
            body=body,
            status=meta.get("status", "active"),
            created=meta.get("created"),
            updated=meta.get("updated"),
            extra=extra,
        )

    def iter_facts(self):
        for kind in KINDS:
            d = self.root / kind
            if not d.is_dir():
                continue
            for p in sorted(d.glob("*.md")):
                yield self.read(p)

    def get(self, fact_id: str) -> Fact | None:
        for fact in self.iter_facts():
            if fact.id == fact_id:
                return fact
        return None
