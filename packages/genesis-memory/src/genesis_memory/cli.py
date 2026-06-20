"""`genesis` — the AI's plain-language control surface (Phase 1: status).

Monitoring should not mean "go read logs." `genesis status` reports memory health
in one glance. More verbs (autonomy, pause/resume, rollback, grant, resync) land
with the loops and broker.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from . import __version__, index as index_mod
from .vault import Vault


def _vault_root(arg: str | None) -> Path:
    if arg:
        return Path(arg).expanduser()
    env = os.environ.get("GENESIS_ROOT")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".genesis" / "vault"


def cmd_status(args) -> int:
    root = _vault_root(args.vault)
    print(f"genesis-memory {__version__}")
    print(f"vault: {root}")
    if not root.exists():
        print("status: no vault yet — run onboarding to give the AI a home")
        return 0

    vault = Vault(root)
    facts = list(vault.iter_facts())
    text, shrunk = index_mod.enforce_budget(facts)
    nbytes = len(text.encode("utf-8"))

    print(f"facts: {len(facts)}")
    by_kind: dict[str, int] = {}
    for f in facts:
        by_kind[f.kind] = by_kind.get(f.kind, 0) + 1
    if by_kind:
        print("  " + ", ".join(f"{k}: {n}" for k, n in sorted(by_kind.items())))
    note = " (shrunk to fit)" if shrunk else ""
    print(f"index: {nbytes} / {index_mod.DEFAULT_MAX_BYTES} bytes{note}")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="genesis", description="Genesis AI control surface")
    p.add_argument("--version", action="version", version=f"genesis-memory {__version__}")
    sub = p.add_subparsers(dest="cmd")
    ps = sub.add_parser("status", help="show the AI's memory health")
    ps.add_argument("--vault", default=None, help="vault root (default: $GENESIS_ROOT or ~/.genesis/vault)")
    ps.set_defaults(func=cmd_status)

    args = p.parse_args(argv)
    if not getattr(args, "func", None):
        p.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
