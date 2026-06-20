"""A Fact: one unit of memory, one file in the vault.

`kind` is a closed enum so retrieval and consolidation can reason about type.
`soul` is the identity-load-bearing kind (self-notes); like every other kind it
ships with zero instances. The slug rules mirror the reference vault: reserved
leading underscore is blocked so internal/meta files never collide with facts.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Categories of *evidence*, never of personality. Content-free by construction.
KINDS = ("user", "feedback", "project", "reference", "soul")
STATUSES = ("active", "dormant", "archived")

_SLUG = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


class FactError(ValueError):
    """Raised when a Fact would violate the schema (bad slug/kind/status)."""


def validate_slug(slug: str) -> str:
    if slug.startswith("_"):
        raise FactError(f"reserved leading underscore: {slug!r}")
    if not _SLUG.match(slug):
        raise FactError(f"invalid slug (allowed: [a-z0-9][a-z0-9_-]*): {slug!r}")
    return slug


@dataclass
class Fact:
    id: str
    kind: str
    description: str
    body: str = ""
    status: str = "active"
    created: str | None = None
    updated: str | None = None
    # any other frontmatter keys are preserved verbatim (tolerant by design)
    extra: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_slug(self.id)
        if self.kind not in KINDS:
            raise FactError(f"unknown kind {self.kind!r} (allowed: {KINDS})")
        if self.status not in STATUSES:
            raise FactError(f"unknown status {self.status!r} (allowed: {STATUSES})")
