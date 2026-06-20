"""Genesis memory subsystem.

The canonical store is a vault of one-fact-per-file markdown with YAML-ish
frontmatter. Derived stores (sqlite/FTS5, vectors) come later and rebuild from
this. Nothing here ships content: it ships the *schema*, the *write path*, and
the *budget discipline*. A fresh vault is empty, and empty is correct.
"""

__version__ = "0.0.1"

from .fact import Fact, FactError, KINDS, STATUSES
from .vault import Vault
from .tiers import Continuity, Perishable
from . import frontmatter, index, tiers

__all__ = [
    "Fact",
    "FactError",
    "KINDS",
    "STATUSES",
    "Vault",
    "Continuity",
    "Perishable",
    "frontmatter",
    "index",
    "tiers",
    "__version__",
]
