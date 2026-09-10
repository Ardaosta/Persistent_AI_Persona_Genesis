"""`genesis-headlines` — the control surface for the orientation layer.

Verbs:

  new <slug>       scaffold a cluster (alias/path net + headline stubs)
  list             every cluster with its alias/path counts
  resolve <sig>    which clusters a signal touches (bodies to stdout; --json)
  surface          the dedup'd, wrapped block a host injects before a turn
  check            lint clusters (well-formed? still placeholder?)

The `surface` verb is what a host wires into its "before the turn acts" event. It
accepts the signal three ways so any engine/harness can call it:

  * positional args / --signal      a plain signal string
  * --cwd PATH                      folded into the signal (drift-proof path match)
  * --hook-json                     read a hook payload as JSON on stdin and pull
                                    prompt + cwd + session_id out of it (so it can
                                    be a Claude Code hook command with no shim)
  * (no signal given)               read the signal as plain text from stdin
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from typing import Optional, Tuple

from . import __version__, frontmatter
from .resolver import resolve
from .scaffold import new_cluster
from .store import cluster_paths, headlines_dir
from .surface import surface


def cmd_new(a) -> int:
    try:
        dest = new_cluster(
            a.slug,
            aliases=a.alias or None,
            paths=a.path or None,
            title=a.title,
            today=date.today().isoformat(),
            dir=a.dir,
        )
    except (FileExistsError, ValueError) as e:
        print(f"REFUSED: {e}", file=sys.stderr)
        return 1
    d = dest.parent
    rel = dest.name
    print(f"created {d}/{rel}")
    print("NEXT: fill in the real headlines (the huge things), then commit.")
    alias0 = (a.alias or [dest.stem])[0]
    print(f"Verify a session will match it:  genesis-headlines resolve '{alias0}'")
    return 0


def cmd_list(a) -> int:
    d = headlines_dir(a.dir)
    paths = cluster_paths(a.dir)
    print(f"headlines: {d}")
    if not paths:
        print("  (none yet — `genesis-headlines new <slug>` to start one)")
        return 0
    for p in paths:
        meta, _ = frontmatter.parse(p.read_text(encoding="utf-8"))
        na = len(meta.get("aliases", []))
        np = len([x for x in meta.get("paths", []) if not x.startswith("<")])
        print(f"  {p.stem:<32} {na:>2} aliases  {np:>2} paths")
    return 0


def cmd_resolve(a) -> int:
    signal = _signal_from_args(a)[0]
    hits = resolve(signal, dir=a.dir)
    if a.json:
        print(json.dumps([{"cluster": h.slug, "body": h.body} for h in hits]))
    elif hits:
        print("\n\n".join(h.body for h in hits))
    return 0


def cmd_surface(a) -> int:
    signal, session_id = _signal_from_args(a)
    result = surface(signal, session_id, dir=a.dir, dedup=not a.no_dedup)
    if a.json:
        print(json.dumps({
            "matched": result.matched,
            "clusters": result.clusters,
            "suppressed": result.suppressed,
            "text": result.text,
        }))
    elif result.text:
        print(result.text)
    return 0


def cmd_check(a) -> int:
    paths = cluster_paths(a.dir)
    problems = 0
    for p in paths:
        meta, body = frontmatter.parse(p.read_text(encoding="utf-8"))
        issues = []
        if not meta.get("aliases"):
            issues.append("no aliases (nothing will match it)")
        real_paths = [x for x in meta.get("paths", []) if not x.startswith("<")]
        if not real_paths:
            issues.append("no real paths (cwd matching disabled)")
        if "Replace this." in body:
            issues.append("still has placeholder headlines")
        if issues:
            problems += 1
            print(f"  {p.stem}: " + "; ".join(issues))
    if a.signal:
        hits = resolve(a.signal, dir=a.dir)
        names = ", ".join(h.slug for h in hits) or "(none)"
        print(f"signal {a.signal!r} matches: {names}")
    if not problems:
        print(f"ok: {len(paths)} cluster(s), all well-formed")
    return 1 if problems else 0


def _signal_from_args(a) -> Tuple[str, str]:
    """Assemble (signal, session_id) from args / stdin, per the input modes."""
    session_id = getattr(a, "session", "") or ""
    if getattr(a, "hook_json", False):
        try:
            payload = json.load(sys.stdin)
        except Exception:
            return "", session_id
        prompt = (payload.get("prompt") or payload.get("user_prompt") or "")[:4000]
        cwd = payload.get("cwd", "")
        session_id = session_id or payload.get("session_id", "") or ""
        return f"{prompt} {cwd}".strip(), session_id
    parts = list(getattr(a, "signal", None) or [])
    signal = " ".join(parts).strip()
    if not signal and not sys.stdin.isatty():
        signal = sys.stdin.read().strip()
    cwd = getattr(a, "cwd", None)
    if cwd:
        signal = f"{signal} {cwd}".strip()
    return signal, session_id


def _add_signal_flags(p) -> None:
    p.add_argument("signal", nargs="*", help="signal text (or read from stdin)")
    p.add_argument("--cwd", help="cwd to fold into the signal (path matching)")
    p.add_argument("--session", help="session id (dedup key for surface)")
    p.add_argument("--hook-json", action="store_true",
                   help="read a hook payload as JSON on stdin")
    p.add_argument("--json", action="store_true", help="machine-readable output")


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="genesis-headlines", description=__doc__)
    ap.add_argument("--version", action="version", version=f"genesis-headlines {__version__}")
    ap.add_argument("--dir", help="headlines dir override (default $GENESIS_ROOT/headlines)")
    sub = ap.add_subparsers(dest="cmd")

    p_new = sub.add_parser("new", help="scaffold a new cluster")
    p_new.add_argument("slug")
    p_new.add_argument("--alias", action="append", default=[], help="a name it goes by (repeatable)")
    p_new.add_argument("--path", action="append", default=[], help="a dir/file it owns (repeatable)")
    p_new.add_argument("--title")
    p_new.set_defaults(func=cmd_new)

    sub.add_parser("list", help="list clusters").set_defaults(func=cmd_list)

    p_res = sub.add_parser("resolve", help="which clusters a signal touches")
    _add_signal_flags(p_res)
    p_res.set_defaults(func=cmd_resolve)

    p_sur = sub.add_parser("surface", help="dedup'd wrapped block to inject")
    _add_signal_flags(p_sur)
    p_sur.add_argument("--no-dedup", action="store_true", help="always surface (host manages dedup)")
    p_sur.set_defaults(func=cmd_surface)

    p_chk = sub.add_parser("check", help="lint clusters; --signal to test a match")
    p_chk.add_argument("--signal", help="a signal to test-resolve")
    p_chk.set_defaults(func=cmd_check)

    return ap


def main(argv: Optional[list] = None) -> int:
    ap = build_parser()
    a = ap.parse_args(argv)
    if not getattr(a, "func", None):
        ap.print_help()
        return 0
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main())
