"""The vault: the canonical, owned, human-readable source of truth.

One fact per file at `<root>/<kind>/<id>.md`. Every durable write goes through
`Vault.write` (the single blessed write path), which stamps timestamps and
serializes via the tolerant frontmatter writer. Reads round-trip back to Facts.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

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

    def write(self, fact: Fact, *, now: str | None = None, warn=None) -> Path:
        """The single blessed write path. `now` is injectable for deterministic tests.

        `warn` is an optional callable receiving one string per reachability
        concern (a body past the semantic window, a description that cannot serve
        as a retrieval trigger). Told here it is an edit; discovered in a report
        weeks later it is archaeology, and the document was unfindable the whole
        time. Warnings only: refusing a long fact would lose the thought, which is
        worse than a thought that is hard to search for.

        Publishes atomically (temp file + os.replace) and preserves `created`
        across updates. Both were found 2026-07-29 by a sibling companion, reading this
        function rather than recalling it, while answering a question about
        concurrent writers.
        """
        stamp = now or _now_iso()
        path = self.path_for(fact)

        if warn is not None:
            # Imported here, not at module scope: reachability imports graph,
            # which imports this module.
            from .reachability import write_warnings
            for msg in write_warnings(fact):
                warn(msg)

        # `created` belongs to the fact's history, not to this write. The agent's
        # remember tool constructs a FRESH Fact on every call, always with
        # created=None, so a caller updating an existing id arrives here looking
        # exactly like a brand-new fact — and the old code duly stamped it as
        # one, silently resetting the original creation date. Nothing errored and
        # nothing logged; the vault just quietly forgot when it had learned
        # something. Recover the real date from what is already on disk.
        if fact.created is None and path.exists():
            try:
                fact.created = self.read(path).created
            except Exception:  # noqa: BLE001 — a corrupt existing file must not block the write
                pass
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

        path.parent.mkdir(parents=True, exist_ok=True)

        # Atomic publish. write_text truncates the target first and then fills it,
        # which leaves a window where the file on disk is a real path containing
        # half a fact. Anything reading concurrently — `recall`, or the boot index
        # build walking the whole tree — can land in that window, and two writers
        # to the same id can interleave and tear it outright. Writing to a temp
        # file in the SAME directory (so the rename stays within one filesystem)
        # and then os.replace-ing it into place closes the window: the swap is
        # atomic on POSIX and Windows alike, a reader sees either the old
        # complete fact or the new one and never a partial, and a same-id race
        # degrades from corruption to clean last-writer-wins.
        tmp = path.with_name(f".{path.name}.{uuid4().hex[:8]}.tmp")
        try:
            tmp.write_text(frontmatter.serialize(meta, fact.body), encoding="utf-8")
            os.replace(tmp, path)
        except Exception:
            tmp.unlink(missing_ok=True)
            raise
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

    def iter_facts(self, *, on_error=None):
        """Every readable fact, skipping the ones that are not.

        The vault is plain markdown on the person's own machine and they are
        encouraged to open it, so a hand-edited file with a space in its name or
        a mangled frontmatter block is an ordinary Tuesday. This used to raise
        out of the generator, which meant ONE bad file took down `status`, the
        index build, and every read path with a traceback: the whole memory
        unreachable because of one typo in a corner of it.

        `on_error(path, exc)` receives each skipped file. Skipping silently would
        be its own bug, so callers that can report get told; the point is that a
        file nobody can parse is the most unreachable a fact can be, and it
        should be NAMED rather than either crashing or vanishing.
        """
        for kind in KINDS:
            d = self.root / kind
            if not d.is_dir():
                continue
            for p in sorted(d.glob("*.md")):
                try:
                    yield self.read(p)
                except Exception as e:  # noqa: BLE001 - one bad file is not a dead vault
                    if on_error is not None:
                        on_error(p, e)

    def get(self, fact_id: str) -> Fact | None:
        for fact in self.iter_facts():
            if fact.id == fact_id:
                return fact
        return None
