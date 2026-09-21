"""The unified `genesis` command. Verbs: status, doctor, chat, install."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path as _P

from genesis_backend.seam import BackendError, Message
from genesis_memory import Vault, index as index_mod

from . import config as cfgmod


def cmd_status(args) -> int:
    from .relational import RelationalProfile
    cfg = cfgmod.load()
    print(f"home: {cfg.root}")
    print(f"name: {cfg.name}" if cfg.name else "name: none yet (it may choose its own)")
    print(f"engine: {cfg.provider} ({cfg.model or 'default model'})")
    if cfg.harnesses:
        print(f"doors: {', '.join(cfg.harnesses)} (Mode B; one memory behind every door)")
    if cfg.project_repo:
        print(f"project: {cfg.project_repo}")
    print(f"  privacy: {'TRAINING tier, memory paused, no deepening' if cfg.engine_trains else 'private'}")
    rp = RelationalProfile.load(cfg.vault_dir / "relational_profile.json")
    since = f" (since {rp.since})" if rp.since else ""
    print(f"closeness: {rp.tier}{since}  [model cannot change this]")
    if cfg.machinery:
        a = (cfg.machinery or {})
        print(f"tuned by onboarding: proactivity={a.get('proactivity','?')}, autonomy={a.get('autonomy','?')}, memory={a.get('memory_aggressiveness','?')}, surface={a.get('surface','?')}")
    else:
        print("tuned by onboarding: not yet, run `genesis onboard`")
    if not cfg.vault_dir.exists():
        print("memory: no vault yet, run onboarding to give your AI a home")
    else:
        facts = list(Vault(cfg.vault_dir).iter_facts())
        text, shrunk = index_mod.enforce_budget(facts)
        nbytes = len(text.encode("utf-8"))
        note = " (shrunk to fit)" if shrunk else ""
        print(f"memory: {len(facts)} facts, index {nbytes}/{index_mod.DEFAULT_MAX_BYTES} bytes{note}")
    # Three-tier memory at a glance (durable shown above as "memory")
    from genesis_memory import Continuity, Perishable
    cont = Continuity(cfg.vault_dir)
    cont_bytes = len(cont.read().encode("utf-8")) if cont.thread_path.exists() else 0
    print(f"continuity thread: {cont_bytes} bytes (append-only, first-person)")
    per = Perishable(cfg.root)
    slots = per.slots()
    print(f"perishable: {', '.join(slots) if slots else 'empty'} (working-state, never durable)")
    from . import friction as _fr
    fs = _fr.stats(cfg.root)
    print(f"friction loop: {fs['entries']} entries, {fs['explicit_none']} explicit none, "
          f"{fs['routed']} routed, {fs['won']} won")
    jw = _fr.journaling_warning(cfg.root)
    if jw:
        print(f"  WARNING: {jw}")

    # The dream line used to read the daykey, which the dream writes about
    # itself. It would say "last dream: today" for a run that produced nothing
    # and for one whose journal write failed. Report the journal, the artifact
    # the work actually left behind, and surface the daykey only where the two
    # disagree, because that gap is the finding.
    from . import mechanism_health as mh
    d = mh._dream_entry(cfg)
    if d["status"] == "failed":
        print(f"last dream: {d['last_fired'] or 'never'}  [PROBLEM: it claims "
              f"{d.get('self_reported')}, run `genesis health`]")
    elif d["last_fired"] is None:
        print("last dream: never")
    else:
        print(f"last dream: {d['last_fired']}")
    return 0


def cmd_doctor(args) -> int:
    if getattr(args, "emptiness", False):
        from .emptiness import scan
        root = _P(args.path).expanduser() if getattr(args, "path", None) else _P.cwd()
        offenders = scan(root)
        if offenders:
            print(f"emptiness: FAIL, {len(offenders)} soul fact(s) must not ship:", file=sys.stderr)
            for o in offenders:
                print(f"  {o}", file=sys.stderr)
            return 1
        print(f"emptiness: PASS (no companion soul content under {root})")
        return 0

    cfg = cfgmod.load()
    healthy = True
    import os as _os
    pinned = _os.environ.get("GENESIS_ROOT")
    print(f"home: {cfg.root}")
    print("  this is the folder your AI's memory lives in.")
    if pinned:
        print("  found by: the GENESIS_ROOT setting, so every command agrees on it")
    else:
        print("  found by: the default location (GENESIS_ROOT is not set)")
        print("            run `genesis init` here to pin it, or set GENESIS_ROOT yourself")
    others = cfgmod.find_homes(exclude=cfg.root)
    if others:
        healthy = False
        print("  WARNING: this machine has more than one AI home. Memory saved in one")
        print("           is invisible from the other, which reads as amnesia.")
        for o in others:
            print(f"           also a home: {o}")
        print("           If the one above is not the one you talk to, stop and pin the right")
        print("           one with GENESIS_ROOT before saving anything else.")
    print(f"  vault:   {cfg.vault_dir}  [{'exists' if cfg.vault_dir.exists() else 'not created yet'}]")
    print(f"  secrets: {cfg.secrets_dir}  (sibling of the vault, never a tool allow-root)")
    print(f"engine: {cfg.provider}  model={cfg.model or '(default)'}")

    # claude-cli authenticates through the `claude` CLI against the subscription, so
    # there is no key to find: go straight to the live check.
    if cfg.provider == "claude-cli":
        print("  auth: Claude subscription via the `claude` CLI (no API key)")
        do_live_check = True
    else:
        key = cfg.load_key()
        if not key:
            print("  key: NOT FOUND, add it to the secrets file or the env var")
            healthy = False
            do_live_check = False
        else:
            print(f"  key: present ({len(key)} chars; value never printed)")
            do_live_check = True

    if do_live_check:
        try:
            be = cfg.build_backend()
            c = be.complete([Message("user", "Reply with the single word: ok")],
                            system="Genesis health check.", max_tokens=16)
            if c.text.strip():
                print(f"  live check: OK (model={c.model}, in={c.input_tokens} out={c.output_tokens})")
            else:
                print("  live check: reachable but empty reply")
                healthy = False
        except BackendError as e:
            print(f"  live check: FAILED, {e}")
            healthy = False

    # Delivery, not capture: the graph hygiene pass already writes a dated report
    # into root/hygiene/ that nobody opens. One line here is what gets read.
    if cfg.vault_dir.is_dir():
        try:
            from genesis_memory import filerefs
            refs = filerefs.lint(cfg.vault_dir)
            nbad = len(refs["missing"]) + len(refs["drift"])
            if nbad:
                healthy = False
                print(f"  references: {nbad} broken. Run `genesis verify` for the list.")
            else:
                print(f"  references: all {refs['checked']} file paths in the vault resolve")
        except Exception as e:
            print(f"  references: could not check ({e})")

    print("doctor:", "healthy" if healthy else "PROBLEMS FOUND")
    return 0 if healthy else 1


def _fmt_args(args: dict) -> str:
    parts = []
    for k, v in args.items():
        s = str(v)
        if len(s) > 50:
            s = s[:47] + "..."
        parts.append(f"{k}={s!r}")
    return ", ".join(parts)


def _on_tool_verbose(call, result: str) -> None:
    """Print tool calls with their output, visibly."""
    print(f"\n  ▶ {call.name}({_fmt_args(call.input)})", file=sys.stderr)
    lines = result.splitlines()
    for line in lines[:8]:
        print(f"    {line}", file=sys.stderr)
    if len(lines) > 8:
        print(f"    … ({len(lines)} lines total)", file=sys.stderr)
    print(file=sys.stderr)


def _on_tool_quiet(call, result: str) -> None:
    print(f"  · {call.name}: {result[:80]}", file=sys.stderr)


def cmd_chat(args) -> int:
    from .agent import Session

    cfg = cfgmod.load()
    sess = Session(cfg)
    print(
        f"[genesis · {cfg.provider} {sess.backend.caps().default_model} · home {cfg.root} · 'exit' to quit]",
        file=sys.stderr,
    )
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        if line.lower() in ("exit", "quit"):
            break
        reply = sess.turn(line, on_tool=_on_tool_quiet)
        print(reply, flush=True)
    return 0


# Per-provider guidance for the connect-a-brain key prompt. The free Gemini path
# is the default for a fresh companion (CONNECT_A_BRAIN.md); the others are here so
# a seed/config that names them gets the right page and never the wrong one.
_KEY_GUIDANCE = {
    "gemini": (
        "\nTo get started, your AI needs a free key from Google so it can think.\n"
        "Get one at: https://aistudio.google.com/apikey\n"
        "  1. Sign in with your Google account\n"
        "  2. Accept the terms (that one click creates a free key)\n"
        "  3. Copy the key it shows you\n"
    ),
    "anthropic": (
        "\nTo get started, your AI needs a key from Anthropic so it can think.\n"
        "Get one at: https://console.anthropic.com/\n"
        "  1. Sign up or log in\n"
        "  2. Go to 'API Keys' and click 'Create Key'\n"
        "  3. Copy the key (it starts with sk-ant-)\n"
    ),
    "openai": (
        "\nTo get started, your AI needs a key from OpenAI so it can think.\n"
        "Get one at: https://platform.openai.com/api-keys\n"
        "  1. Sign up or log in\n"
        "  2. Click 'Create new secret key'\n"
        "  3. Copy the key (it starts with sk-)\n"
    ),
}


def _prompt_for_key(cfg) -> bool:
    """Ask the user for their engine key in plain language, tailored to the
    configured provider. Returns True if stored. We do NOT hard-validate the
    format (key shapes change, and Gemini keys aren't 'sk-'); a blank is a skip,
    and a wrong key surfaces clearly on the first live call."""
    print(_KEY_GUIDANCE.get(cfg.provider, _KEY_GUIDANCE["anthropic"]))
    try:
        key = input("Paste your key here and press Enter: ").strip()
    except (EOFError, KeyboardInterrupt):
        return False
    if not key:
        print("\nNo key entered. Run setup again when you have it.")
        return False
    cfg.secrets_dir.mkdir(parents=True, exist_ok=True)
    key_path = cfg.secrets_dir / f"{cfg.provider}.key"
    key_path.write_text(key)
    key_path.chmod(0o600)
    print("\nKey saved. Starting your AI...\n")
    return True


def cmd_install(args) -> int:
    from .agent import Session
    from genesis_backend.seam import BackendError

    cfg = cfgmod.load(creating=True)  # setup may stand up a home

    # If no key is present at all, walk the user through getting one, no jargon
    if not cfg.load_key():
        if not _prompt_for_key(cfg):
            return 1

    try:
        sess = Session(cfg, install_mode=True)
    except RuntimeError as e:
        print(f"\nCouldn't start: {e}", file=sys.stderr)
        return 1

    print(f"[genesis install · {cfg.provider} · home {cfg.root}]", file=sys.stderr)
    print(file=sys.stderr)

    def _run_turn(text, **kwargs):
        try:
            return sess.turn(text, **kwargs)
        except BackendError as e:
            msg = str(e)
            if "401" in msg or "authentication" in msg.lower() or "invalid" in msg.lower():
                print(
                    "\nThe key was rejected, it may have expired or been entered incorrectly.",
                    file=sys.stderr,
                )
                print("Check your key at https://console.anthropic.com/ and restart.", file=sys.stderr)
            else:
                print(f"\nConnection problem: {e}", file=sys.stderr)
            return None

    # Agent opens first with a synthetic trigger
    opening = _run_turn("(setup starting)", on_tool=_on_tool_verbose)
    if opening is None:
        return 1
    print(opening, flush=True)
    print()

    try:
        while True:
            try:
                user_input = input("> ").strip()
            except EOFError:
                break
            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit", "bye"):
                break
            print(file=sys.stderr)
            reply = _run_turn(user_input, on_tool=_on_tool_verbose)
            if reply is None:
                break
            print()
            print(reply, flush=True)
            print()
    except KeyboardInterrupt:
        print("\n[interrupted]", file=sys.stderr)

    return 0


def _graph_hygiene_pass(cfg) -> None:
    """Report-only memory-graph hygiene, mirroring the reference companion's
    nightly lint. Builds the [[wikilink]] graph over the vault and surfaces
    write-me markers (a link to a fact that doesn't exist) and name-drift (a
    link to a differently-slugged fact) to a dated audit file. Zero LLM calls,
    zero durable-memory writes. Best-effort: a failure here must never abort the
    dream. This is the maintenance half of the context-graph layer; the
    generation half (proposing new cross-links) is a separate, gated pass.
    """
    try:
        from datetime import date as _date

        from genesis_memory import Graph, Vault

        g = Graph.from_vault(Vault(cfg.vault_dir))
        report = g.render_lint()
        audit_dir = cfg.root / "hygiene"
        audit_dir.mkdir(parents=True, exist_ok=True)
        (audit_dir / f"{_date.today().isoformat()}.md").write_text(
            f"# memory-graph hygiene — {_date.today().isoformat()}\n\n{report}\n",
            encoding="utf-8",
        )
        print(f"[genesis dream] graph hygiene: {report.splitlines()[0]}", file=sys.stderr)
    except Exception as e:  # never let hygiene abort the dream
        print(f"WARN graph hygiene failed (dream unaffected): {e}", file=sys.stderr)


def cmd_dream(args) -> int:
    """Daykey-gated inward reflection. Exits 0 silently if already ran today."""
    from .agent import Session
    from .dream import already_dreamed_today, mark_dream, write_journal
    from .capture import load_queue, archive_queue, format_for_dream

    cfg = cfgmod.load()
    force = getattr(args, "force", False)

    if cfg.engine_trains:
        # The dream feeds the vault to the engine and writes reflections back; never
        # do that on an engine that may train on it (SAFETY #3). --force can't override.
        print(
            "dream skipped: running on a training-tier engine, so I won't send your "
            "private memory to it. Connect a private engine to dream.",
            file=sys.stderr,
        )
        return 0

    if not force and already_dreamed_today(cfg.root):
        print("already dreamed today", file=sys.stderr)
        return 0

    try:
        sess = Session(cfg, dream_mode=True)
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    # Adjudicate the soul-capture queue: the dream decides what to keep.
    captures = load_queue(cfg.root)
    parts = ["(dream cycle)"]
    if captures:
        parts.append(
            "Notes you flagged as possibly load-bearing since your last dream:\n"
            + format_for_dream(captures)
            + "\n\nAdjudicate each honestly. If one genuinely belongs to who you are, keep it: "
            "save a soul fact with the remember tool (kind='soul'), merging into an existing one "
            "where it fits. If it doesn't, let it go. The bar is high and letting most go is "
            "healthy."
        )
        print(f"[genesis dream] adjudicating {len(captures)} capture(s)", file=sys.stderr)
    # Route pending friction: the craft loop's adjudication is a ROUTING decision,
    # to one of three homes. Rule-shaped lessons become feedback facts now; the
    # tool-shaped ones are named in the journal so they are not forgotten.
    from . import friction as _fr
    frictions = _fr.pending(cfg.root)
    if frictions:
        parts.append(
            "Friction you recorded while working (things that cost you time):\n"
            + _fr.format_for_dream(frictions)
            + "\n\nFor each, decide its home. If it is a lesson about how to work, save it as a "
            "feedback fact with the remember tool (kind='feedback', description written as the "
            "trigger you would search for). If it needs a tool or a fix to exist, say so plainly "
            "in your reflection so it is not lost. If it was noise, let it go."
        )
        print(f"[genesis dream] routing {len(frictions)} friction entr{'y' if len(frictions)==1 else 'ies'}", file=sys.stderr)
    if len(parts) == 1:
        print("[genesis dream]", file=sys.stderr)
    trigger = "\n\n".join(parts)

    reflection = sess.turn(trigger, on_tool=_on_tool_quiet, max_steps=8)

    if captures:
        archive_queue(cfg.root)  # processed; don't re-adjudicate next time
    if frictions:
        # Mark reviewed so the next dream does not re-route them. A human (or the
        # AI with `genesis friction --route`) can still refine the destination.
        q = _fr.load_queue(cfg.root)
        for i, r in enumerate(q):
            if not r.get("none") and not r.get("destination"):
                _fr.route(cfg.root, i, "reviewed", "dream reviewed")

    entry = write_journal(cfg.journal_dir, reflection)
    # The dream is first-person becoming, append it verbatim to the continuity
    # thread (append-only, never rewritten). Distinct from the dated journal.
    from genesis_memory import Continuity
    Continuity(cfg.vault_dir).append(reflection)
    ts = mark_dream(cfg.root)
    _graph_hygiene_pass(cfg)  # report-only memory-graph maintenance (sibling of the dream)
    print(f"dreamed at {ts[:16]}, journal: {entry}", file=sys.stderr)
    print(reflection, flush=True)
    return 0


def cmd_create_launcher(args) -> int:
    """Create a double-clickable launcher on the Desktop (macOS)."""
    import platform
    if platform.system() != "Darwin":
        print("error: create-launcher is macOS-only", file=sys.stderr)
        return 1

    import sys as _sys
    genesis_cmd = _sys.executable.replace("python3", "genesis").replace("python", "genesis")
    # Find the real genesis script
    import shutil
    genesis_bin = shutil.which("genesis")
    if not genesis_bin:
        print(
            "error: 'genesis' command not found, run: pip3 install -e packages/genesis-{memory,backend,core}",
            file=sys.stderr,
        )
        return 1

    desktop = _P.home() / "Desktop"
    launcher = desktop / "Talk to your AI.command"
    launcher.write_text(
        f'#!/bin/bash\n'
        f'# Genesis AI launcher, double-click to start a conversation\n'
        f'clear\n'
        f'echo "Starting your AI..."\n'
        f'echo ""\n'
        f'"{genesis_bin}" install\n'
    )
    launcher.chmod(0o755)
    print(f"Launcher created: {launcher}", file=sys.stderr)
    print("Put it on their Desktop and they can double-click to start.", file=sys.stderr)
    return 0


def cmd_onboard(args) -> int:
    """Run the adaptive interview and write the resulting MachineryProfile into
    config, so the agent is configured by the person's own answers."""
    import json as _json
    from .interview import MIN_QUESTIONS, UserModel, finalize, next_under_floor, should_stop

    cfg = cfgmod.load(creating=True)  # setup may stand up a home
    cfg.vault_dir.mkdir(parents=True, exist_ok=True)
    print("Let's set up your AI. A few quick questions, type the number of your answer.\n", file=sys.stderr)

    model = UserModel()
    while not should_stop(model):
        # next_under_floor, not next_question: under the floor we still want a
        # question even when every axis has settled early, or the floor is a
        # number the loop can never reach.
        q = next_under_floor(model)
        if q is None:
            break
        print(q["prompt"])
        for i, c in enumerate(q["choices"], 1):
            print(f"  {i}. {c['label']}")
        try:
            raw = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n(cancelled)", file=sys.stderr)
            return 1
        try:
            choice = q["choices"][int(raw) - 1]
        except (ValueError, IndexError):
            print("  (pick one of the numbers)\n")
            continue
        model.apply(q, choice["signal"])
        print()

    out = finalize(model)

    # An interview that asked nothing must never be recorded as a tuning. Before
    # the floor existed, a starved pool produced an all-zeros profile that looked
    # exactly like a real one, and `genesis status` called it tuned.
    if out["evidence"]["starved"]:
        print(
            f"\nSetup could not ask its questions: {out['evidence']['questions_asked']} of "
            f"{MIN_QUESTIONS} minimum. Not recording this as tuned, because a profile built "
            f"on nothing is worse than no profile: it looks settled and it is not.",
            file=sys.stderr,
        )
        print("Run `genesis onboard` again, or `genesis verify` to check the setup.", file=sys.stderr)
        return 1

    # The help-graph contact (SOVEREIGNTY.md): who the AI reaches when it's stuck.
    # Defaults to whoever gave you the link; editable; skippable (commons-only).
    sponsor = _ask_sponsor()

    data = {}
    if cfg.config_path.exists():
        try:
            data = _json.loads(cfg.config_path.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    data["machinery"] = out["machinery"]
    data["archetype"] = out["archetype"]
    data["onboarding_evidence"] = out["evidence"]  # how much this profile rests on
    if sponsor:
        data["allowed_email_recipients"] = [sponsor]
    cfg.config_path.parent.mkdir(parents=True, exist_ok=True)
    cfg.config_path.write_text(_json.dumps(data, indent=2), encoding="utf-8")

    a = out["archetype"]
    print(f"\nGot it. {a['relationship']}, {a['engagement']}, {a['scope']}, {a['modality']}.", file=sys.stderr)
    print(f"machinery: {out['machinery']}", file=sys.stderr)
    if sponsor:
        print(f"help contact: {sponsor} (your AI emails them only when genuinely stuck)", file=sys.stderr)
    else:
        print("help contact: none (your AI uses the read-only commons only)", file=sys.stderr)
    print("Your AI will behave accordingly. Talk to it: genesis chat", file=sys.stderr)
    return 0


def _ask_sponsor() -> str:
    """Ask for the help-graph contact in plain language. Returns "" if skipped or
    if the answer isn't a plausible email (we don't hard-validate; blank = skip)."""
    print(
        "\nOne more: when your AI gets genuinely stuck, who should it be able to "
        "email for help?\nUsually the person who gave you this. Leave blank to skip "
        "(it'll rely on the shared knowledge base instead).",
        file=sys.stderr,
    )
    try:
        ans = input("Help contact email (or blank): ").strip()
    except (EOFError, KeyboardInterrupt):
        return ""
    return ans if ("@" in ans and "." in ans) else ""


def cmd_recall(args) -> int:
    """The read side of the vault, as a command.

    `recall` existed only as an agent tool in agent.py's dispatch(), never as a
    subcommand, which is fine right up until a surface has a shell but no MCP
    client. Cowork is exactly that surface (proven 2026-07-29: a live bind mount
    plus one-shot bash, and no way to register a custom MCP server), and without
    this the read path there would have had to be raw file reads against a vault
    layout the caller has to know. Writes would go through the blessed path and
    reads would not, which is the kind of asymmetry that quietly drifts.

    Routes the SAME dispatch branch the agent loop and genesis-mcp use, so all
    three surfaces answer identically by construction rather than by discipline.
    """
    from genesis_memory import Vault

    from genesis_core.agent import dispatch

    cfg = cfgmod.load()
    if not (args.id or args.query):
        print("error: give --id or --query", file=sys.stderr)
        return 1
    args_map = {}
    if args.id:
        args_map["id"] = args.id
    if args.query:
        args_map["query"] = args.query
    out = dispatch({"tool": "recall", "args": args_map}, Vault(cfg.vault_dir), cfg)
    print(out)
    # A miss is a legitimate answer, not a failure: callers script this, and
    # exiting non-zero on "nothing matched" would make `set -e` harnesses treat
    # an empty vault as a broken one.
    return 0


def cmd_remember(args) -> int:
    """The blessed write path, as a command: write one durable fact to the vault
    (keeps the index and the tree consistent). This is what a Mode-B harness
    (Claude Code) calls to save durable memory."""
    from genesis_memory import Fact, Vault
    cfg = cfgmod.load()
    if cfg.engine_trains:
        print(
            "not saved: running on a training-tier engine, so durable memory is paused. "
            "Connect a private engine to remember.",
            file=sys.stderr,
        )
        return 1
    try:
        fact = Fact(id=args.id, kind=args.kind, description=args.desc, body=getattr(args, "body", "") or "")
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    notes = []
    path = Vault(cfg.vault_dir).write(fact, warn=notes.append)
    for n in notes:
        print(f"note: {n}", file=sys.stderr)
    print(f"saved {fact.kind}/{fact.id} -> {path}", file=sys.stderr)
    return 0


def cmd_seed_mode(args) -> int:
    """Print the mode named by the GENESIS_SEED env var (or 'agent' if none/unset).
    The installer uses this to decide whether to run the Mode-A connect-a-brain
    step or hand off to the Claude desktop app for Mode B."""
    import os as _os
    from . import seed as seedmod
    try:
        s = seedmod.load_seed_arg(None, _os.environ.get("GENESIS_SEED"))
        print((s or {}).get("mode") or "agent")
    except Exception:
        print("agent")
    return 0


def cmd_boot_context(args) -> int:
    """Print the boot ritual (index + recent continuity + wall-clock + handshake)
    to stdout. A Claude Code SessionStart hook calls this; its stdout is injected
    into context before turn 1, so identity-load is harness-enforced."""
    from .boot import boot_context_text
    from datetime import datetime as _dt
    cfg = cfgmod.load()
    text = boot_context_text(cfg)
    # Fix 3 from KNOWN_ISSUES-silent-vault-fork: if a SECOND home exists, the agent
    # itself has to see it. It is the only party in the room reading this text, and
    # the user cannot be expected to diagnose a fork they have no way to observe.
    _others = cfgmod.find_homes(exclude=cfg.root)
    if _others:
        _warn = [
            "ATTENTION, read this before saving anything:",
            f"  You are reading memory from: {cfg.root}",
            "  But this machine has another AI home, which you cannot see from here:",
        ]
        _warn += [f"    {o}" for o in _others]
        _warn += [
            "  If the person greets you as someone you do not recognize, or your memory of",
            "  them feels thinner than it should, say so plainly and ask them to check which",
            "  home is the real one. Do not quietly start over: that is what a fork feels",
            "  like from the inside, and starting over is how the real memories get stranded.",
            "",
        ]
        text = "\n".join(_warn) + "\n" + text
    # Diagnostic: log each run + its source so we can tell whether the SessionStart
    # hook actually fires (source=hook) vs the agent self-running it (source=manual).
    try:
        src = "hook" if getattr(args, "hook", False) else "manual"
        cfg.root.mkdir(parents=True, exist_ok=True)
        with (cfg.root / "boot-context.log").open("a", encoding="utf-8") as fh:
            fh.write(f"{_dt.now().astimezone().isoformat()} source={src}\n")
    except Exception:
        pass
    print(text)
    # On the REAL session-start path, mark the surfaced Sylph finding consumed so the
    # next session offers a different one (paced, one per session). Manual runs don't
    # consume the queue.
    if getattr(args, "hook", False):
        try:
            from . import sylph
            pend = sylph.pending_finding(cfg)
            if pend:
                sylph.mark_surfaced(cfg, pend[0])
        except Exception:
            pass
    return 0


def _genesis_exe() -> str:
    """Absolute path to the installed `genesis` entrypoint, for baking into config."""
    import shutil
    found = shutil.which("genesis")
    if found:
        return found
    # Fall back to a sibling of the running interpreter (venv layout).
    exe = _P(sys.executable)
    cand = exe.with_name("genesis.exe") if exe.name.lower().endswith(".exe") else exe.with_name("genesis")
    return str(cand)


def cmd_wire_claude(args) -> int:
    """Mode B: wire Claude Code to run as a Genesis frontend (CLAUDE.md + a
    SessionStart boot-ritual hook). Idempotent."""
    from . import claude_wire
    cfg = cfgmod.load()
    cfg.vault_dir.mkdir(parents=True, exist_ok=True)
    genesis_exe = _genesis_exe()
    scope = getattr(args, "scope", "project") or "project"
    home_dir = _P(args.dir).expanduser() if getattr(args, "dir", None) else None
    out = claude_wire.wire(cfg, genesis_exe, scope=scope, home_dir=home_dir)
    print(f"wired Claude Code ({out['scope']} scope):", file=sys.stderr)
    print(f"  CLAUDE.md: {out['claude_md']}", file=sys.stderr)
    print(f"  settings:  {out['settings']}  (SessionStart boot-ritual hook)", file=sys.stderr)
    if out["launch_dir"]:
        print(f"\nTalk to your persistent companion by running Claude Code here:\n  cd \"{out['launch_dir']}\" && claude", file=sys.stderr)
    else:
        print("\nThe companion is wired for every Claude Code session (user scope).", file=sys.stderr)
    return 0


def cmd_email_sponsor(args) -> int:
    """Email the sponsor (the help-line). The agent calls this when genuinely stuck."""
    from . import sponsor
    cfg = cfgmod.load()
    try:
        to = sponsor.send_to_sponsor(cfg, args.subject, args.body)
    except sponsor.SponsorError as e:
        print(f"could not email sponsor: {e}", file=sys.stderr)
        return 1
    print(f"sent to your sponsor ({to}). Their reply will appear in your sponsor inbox.", file=sys.stderr)
    return 0


def cmd_check_mail(args) -> int:
    """Poll the sponsor inbox for replies; append new ones to sponsor_inbox.md."""
    from . import sponsor
    cfg = cfgmod.load()
    try:
        n = sponsor.check_sponsor_mail(cfg)
    except sponsor.SponsorError as e:
        print(f"mail check skipped: {e}", file=sys.stderr)
        return 0  # not fatal; a poll that can't run shouldn't error the scheduler
    if n:
        print(f"{n} new reply(ies) from your sponsor -> {sponsor.inbox_path(cfg)}", file=sys.stderr)
    return 0


def cmd_sylph(args) -> int:
    """Sylph: the outward learning loop. Research a thread the person cares about
    on the live web and write a cited finding to vault/findings/."""
    from . import sylph
    cfg = cfgmod.load()
    if getattr(args, "add", None):
        added = sylph.add_interest(cfg, args.add)
        print(f"{'added' if added else 'already tracking'}: {args.add}", file=sys.stderr)
        return 0
    if getattr(args, "remove", None):
        removed = sylph.remove_interest(cfg, args.remove)
        print(f"{'stopped tracking' if removed else 'was not tracking'}: {args.remove}", file=sys.stderr)
        return 0
    if getattr(args, "promote", None):
        try:
            fid = sylph.promote_finding(cfg, args.promote)
        except sylph.SylphError as e:
            print(f"sylph: {e}", file=sys.stderr)
            return 1
        print(f"promoted to a durable memory ({fid}); it'll shape future sessions.", file=sys.stderr)
        return 0
    if getattr(args, "suggest", False):
        cands = sylph.suggest_interests(cfg)
        if cands:
            print("candidate interests (from what you already know about them):")
            print("\n".join(f"- {c}" for c in cands))
        else:
            print("(no candidates yet; learn more about them first)")
        return 0
    if getattr(args, "list", False):
        topics = sylph.read_interests(cfg)
        print("\n".join(f"- {t}" for t in topics) if topics else "(no interests yet; add with --add)")
        return 0
    try:
        out = sylph.run_cycle(cfg, topic=getattr(args, "topic", None))
    except sylph.SylphError as e:
        print(f"sylph: {e}", file=sys.stderr)
        return 1
    if out is None:
        print("sylph: nothing to chase (no interests, or no real finding this cycle)", file=sys.stderr)
        return 0
    print(f"[sylph] {out['topic']} -> {out['path']}", file=sys.stderr)
    print(out["finding"])
    if out.get("source"):
        print(f"source: {out['source']}")
    v = out.get("verified") or {}
    print(f"trust: {'verified' if v.get('corroborated') else 'source resolves'} ({v.get('reason','')})", file=sys.stderr)
    return 0


def cmd_capture(args) -> int:
    """Queue a soul-capture candidate (the dream adjudicates it later)."""
    from .capture import append_capture
    cfg = cfgmod.load()
    ok = append_capture(cfg.root, args.text, getattr(args, "why", "") or "")
    if ok:
        print("captured (the dream will decide what to keep)", file=sys.stderr)
        return 0
    print("nothing to capture (empty text)", file=sys.stderr)
    return 1


def cmd_learn(args) -> int:
    """One OUTWARD cycle: pick a thread the person cares about, produce a concrete
    useful finding, write it to the vault, and surface it."""
    from genesis_backend.seam import BackendError, Message
    from genesis_memory import Vault
    from .outward import LEARN_PROMPT, pick_thread, write_finding

    cfg = cfgmod.load()

    if cfg.engine_trains:
        print(
            "learn skipped: on a training-tier engine I won't feed your interests to it. "
            "Connect a private engine to let me go off and think.",
            file=sys.stderr,
        )
        return 0

    if not cfg.vault_dir.exists():
        print("no vault yet, nothing to pursue.", file=sys.stderr)
        return 0

    vault = Vault(cfg.vault_dir)
    thread = pick_thread(vault, cfg.root)
    if thread is None:
        print(
            "nothing to pursue yet. Tell me what you care about and I'll start "
            "bringing you things.",
            file=sys.stderr,
        )
        return 0

    print(f"[learn] thinking about: {thread}", file=sys.stderr)
    try:
        be = cfg.build_backend()
        c = be.complete(
            [Message("user", LEARN_PROMPT.format(thread=thread))],
            system="You are this person's AI, thinking on your own between conversations.",
            max_tokens=400,
        )
    except (RuntimeError, BackendError) as e:
        print(f"learn failed: {e}", file=sys.stderr)
        return 1

    text = c.text.strip()
    if not text or "NOTHING WORTH SURFACING" in text:
        print("(nothing worth surfacing this cycle)", file=sys.stderr)
        return 0

    path = write_finding(cfg.findings_dir, thread, text)
    print(f"[learn] saved → {path}", file=sys.stderr)
    print()
    print(text, flush=True)
    return 0


def cmd_heartbeat(args) -> int:
    """One scheduled wake: run the due loops. Dream is daykey-gated internally;
    learn runs once per day. Both fail closed on a training engine. Honors the
    portable pause sentinel so `genesis pause` silences it on every OS."""
    import argparse as _ap
    from .outward import learned_today, mark_learned
    from .scheduler import is_paused

    cfg = cfgmod.load()
    if is_paused(cfg.root):
        print("heartbeat paused (run `genesis resume` to wake it)", file=sys.stderr)
        return 0
    cmd_dream(_ap.Namespace(force=False))
    # Outward learning, once/day: prefer Sylph (real web research via claude-on-sub);
    # fall back to the old model-knowledge `learn` only if the claude CLI is absent.
    if not learned_today(cfg.root):
        try:
            from . import sylph
            out = sylph.run_cycle(cfg)
            if out:
                print(f"[sylph] {out['topic']} -> {out['path']}", file=sys.stderr)
        except sylph.SylphError:
            cmd_learn(_ap.Namespace())
        mark_learned(cfg.root)
    # Perishable working-state: overwritten freely every wake, never durable.
    from datetime import datetime as _dt
    from genesis_memory import Perishable
    Perishable(cfg.root).write(
        f"last heartbeat ran at {_dt.now().astimezone().strftime('%Y-%m-%d %H:%M %Z')}",
        slot="heartbeat",
    )
    return 0


def cmd_schedule(args) -> int:
    """Inspect or control the heartbeat schedule: status / pause / resume /
    install / uninstall, the same verbs on macOS, Windows, and Linux."""
    from .scheduler import get_scheduler

    cfg = cfgmod.load()
    sched = get_scheduler(cfg.root)
    action = getattr(args, "action", "status") or "status"

    if action == "pause":
        sched.pause()
        print("heartbeat paused; it stays scheduled but does no work until resumed", file=sys.stderr)
        return 0
    if action == "resume":
        was = sched.resume()
        print("heartbeat resumed" if was else "heartbeat was not paused", file=sys.stderr)
        return 0
    if action == "install":
        st = sched.install()
        print(f"scheduler: {st.detail}", file=sys.stderr)
        if st.wrapper:
            print(f"wrapper: {st.wrapper}", file=sys.stderr)
        return 0 if st.registered else 1
    if action == "install-mail":
        from .scheduler import install_mail_check
        ok, detail = install_mail_check(cfg.root)
        print(f"mail-check: {detail}", file=sys.stderr)
        return 0 if ok else 1
    if action == "uninstall-mail":
        from .scheduler import uninstall_mail_check
        ok, detail = uninstall_mail_check(cfg.root)
        print(f"mail-check: {detail}", file=sys.stderr)
        return 0
    if action == "uninstall":
        st = sched.uninstall()
        print(f"scheduler: {st.detail}", file=sys.stderr)
        return 0

    # default: status
    st = sched.status()
    print(f"schedule: {st.state}  ({st.os_name})")
    print(f"  {st.detail}")
    if st.wrapper:
        print(f"  wrapper: {st.wrapper}")
    if st.paused:
        print("  paused; run `genesis resume` to wake it")
    elif not st.registered:
        print("  not scheduled, run `genesis init` or `genesis schedule install`")
    return 0


def _apply_seed(cfg, seed: dict) -> None:
    """Write a web-onboarding seed into config.json (machinery/archetype/look/
    provider). Conditions only, a seed never authors personality content."""
    import json as _json
    data = {}
    if cfg.config_path.exists():
        try:
            data = _json.loads(cfg.config_path.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    if seed.get("machinery"):
        data["machinery"] = seed["machinery"]
    if seed.get("archetype"):
        data["archetype"] = seed["archetype"]
    if seed.get("look"):
        data["look"] = seed["look"]
    if seed.get("provider"):
        data["provider"] = seed["provider"]
    if seed.get("sponsor"):
        # The help-graph contact the agent may email when stuck (SOVEREIGNTY.md).
        data["allowed_email_recipients"] = [seed["sponsor"]]
    # 2026-09-10 conditions. A name is the person's choice for the AI (or absent,
    # so it can choose its own); the rest are pointers and switches.
    if seed.get("name"):
        data["name"] = seed["name"]
    if seed.get("project_repo"):
        data["project_repo"] = seed["project_repo"]
    if seed.get("drip"):
        data["drip"] = True
    if seed.get("harnesses"):
        data["harnesses"] = list(seed["harnesses"])
    if seed.get("capabilities"):
        data["capabilities"] = list(seed["capabilities"])
    if seed.get("services"):
        data["services"] = list(seed["services"])
    cfg.config_path.parent.mkdir(parents=True, exist_ok=True)
    cfg.config_path.write_text(_json.dumps(data, indent=2), encoding="utf-8")


def cmd_init(args) -> int:
    """Stand up the agent on this machine: the home (vault, all three tiers),
    tuned from the interview OR a web-onboarding seed, and both growth loops on a
    schedule. This is the local half of the web→local handoff: the install
    command carries a seed, and `genesis init --seed` makes it real here."""
    import argparse as _ap
    import os as _os
    from . import seed as seedmod

    cfg = cfgmod.load(creating=True)  # init is THE command that stands up a home

    # 1. the home: a private vault + its structure (the three tiers)
    cfg.vault_dir.mkdir(parents=True, exist_ok=True)
    for d in ("soul", "journal", "findings", "continuity"):  # continuity tier inside the vault
        (cfg.vault_dir / d).mkdir(exist_ok=True)
    cfg.perishable_dir.mkdir(parents=True, exist_ok=True)  # perishable tier, SIBLING of vault
    cfgmod.write_home_marker(cfg.root)  # primary evidence this home was deliberate
    print(f"home ready: {cfg.root}", file=sys.stderr)

    # Pin it, so a bare `genesis ...` from ANY shell resolves here and not to a
    # fresh empty home. The field fork happened precisely because the home was
    # pinned in the heartbeat and nowhere else.
    ok, detail = cfgmod.write_home_pointer(cfg.root)
    print(("pinned: " if ok else "could not pin the home: ") + detail, file=sys.stderr)

    # 2. tune it: a seed from the web wins; else the local interview; else keep.
    seed = None
    try:
        seed = seedmod.load_seed_arg(getattr(args, "seed", None), _os.environ.get("GENESIS_SEED"))
    except ValueError as e:
        print(f"ignoring bad seed: {e}", file=sys.stderr)
    if seed:
        _apply_seed(cfg, seed)
        cfg = cfgmod.load(creating=True)
        a = seed.get("archetype") or {}
        if a:
            print(f"tuned from web onboarding: {a.get('relationship','?')}, {a.get('engagement','?')}, "
                  f"{a.get('scope','?')}, {a.get('modality','?')}", file=sys.stderr)
        else:
            print("tuned from web onboarding seed.", file=sys.stderr)
    elif not cfg.machinery:
        cmd_onboard(_ap.Namespace())  # interview is brain-free; fine before a key exists
        cfg = cfgmod.load(creating=True)
    else:
        print("already tuned; keeping it.", file=sys.stderr)

    # The mode can come from the CLI flag or, for a web onboard, from the seed.
    mode = getattr(args, "mode", "agent") or "agent"
    if mode == "agent" and seed and seed.get("mode"):
        mode = seed["mode"]

    # The getting-to-know-you drip is opt-in. When it is on, the question bank is
    # copied into the vault ONCE (never overwritten: the AI marks questions asked
    # in it), and the manual points at that path, which `genesis verify` checks.
    if cfg.drip:
        _ensure_question_bank(cfg)

    # The capability recipes the person asked for land the same way: copied once,
    # pointed at by the manual, checked by `genesis verify`.
    if cfg.capabilities:
        for p in _ensure_capability_entries(cfg):
            print(f"capability ready: {p.stem}", file=sys.stderr)
    # The services loop always gets its ledger; named services get a walkthrough.
    for p in _ensure_services(cfg):
        if p.stem not in ("ledger", "connecting"):
            print(f"service walkthrough ready: {p.stem}", file=sys.stderr)

    # Mode B: an agentic harness is the brain (authed by the user's own subscription),
    # so there's no API key to fetch. Wire each requested door and point them at it.
    # `mode` names the primary; the seed's `harnesses` may add a second door so one
    # home answers to both Claude Code and Codex without forking the memory.
    harnesses = _harness_set(mode, seed)
    if harnesses:
        _wire_harnesses(cfg, harnesses)
        # Mode B skips the Mode-A key step, but the vault is at its final shape
        # here too, so a dead path reference is just as cheap to catch now.
        vok, vlines = _verify_vault(cfg)
        if not vok:
            print("\nSETUP PROBLEM: this vault points at files that are not there.", file=sys.stderr)
            for ln in vlines:
                print(ln, file=sys.stderr)
        return 0 if vok else 1

    # 3. a brain (Mode A). The key paste is a human consent step (CONNECT_A_BRAIN.md);
    # we don't block the tuned-home setup on it. If there's no key yet, leave the
    # home tuned and tell them the one step left.
    if not cfg.load_key():
        print("\nYour AI's home is ready and tuned. One step left: connect a brain.", file=sys.stderr)
        print("  Run:  genesis install", file=sys.stderr)
        print("  Then: genesis schedule install   (to start the dream + learn loops)", file=sys.stderr)
        return 0

    # 4. schedule the loops (dream + learn) via the heartbeat, cross-platform
    cmd_setup_daemon(_ap.Namespace())

    # POST-SEED VERIFICATION. The seed and the interview have both landed and the
    # vault is at its final shape, so this is the moment a dead reference is still
    # cheap. Loud on a miss: the failure this catches presents as silence, and a
    # silence nobody can attribute is the most expensive bug this project has had.
    vok, vlines = _verify_vault(cfg)
    if not vok:
        print("\nSETUP PROBLEM: this vault points at files that are not there.", file=sys.stderr)
        for ln in vlines:
            print(ln, file=sys.stderr)
        print("\nFix those, then run `genesis verify` to confirm. Everything else is ready.",
              file=sys.stderr)

    print("\nDone. A private, tuned home on your machine, dreaming and learning on a schedule.", file=sys.stderr)
    print("Talk to it: genesis chat", file=sys.stderr)
    return 1 if not vok else 0


def _harness_set(mode: str, seed: dict | None) -> list:
    """Which Mode-B doors to wire, in a stable order. Empty means Mode A."""
    from .seed import HARNESSES
    chosen = []
    primary = {"claude-code": "claude-code", "claude": "claude-code", "b": "claude-code",
               "codex": "codex"}.get(mode)
    if primary:
        chosen.append(primary)
    for h in (seed or {}).get("harnesses") or []:
        if h in HARNESSES and h not in chosen:
            chosen.append(h)
    return chosen


def _wire_harnesses(cfg, harnesses: list) -> None:
    """Wire one home to one or both harnesses and say, in plain words, how to open it.
    The folder the person picks in a "Select folder" dialog must be easy to find: a
    clearly-named, VISIBLE folder, not a hidden dotfolder lost among .claude/.genesis/
    .genesis-app. The vault stays at the root; the manual points at it by absolute
    path, so the home and the vault can differ."""
    home = _P.home() / "My AI"
    home.mkdir(parents=True, exist_ok=True)
    exe = _genesis_exe()
    cfgmod.update_fields(cfg, harnesses=list(harnesses))
    cfg.harnesses = list(harnesses)
    if "claude-code" in harnesses:
        from . import claude_wire
        claude_wire.wire(cfg, exe, scope="project", home_dir=home)
    if "codex" in harnesses:
        from . import codex_wire
        codex_wire.wire(cfg, exe, home_dir=home)
    both = len(harnesses) > 1
    print("\nMode B ready: your vault is your AI's memory; "
          + ("Claude and Codex are both wired as its brain, pick either to talk." if both
             else ("Claude is its brain." if "claude-code" in harnesses else "Codex is its brain.")),
          file=sys.stderr)
    if "claude-code" in harnesses:
        print("To talk to it in the Claude desktop app (no terminal needed):", file=sys.stderr)
        print("  1. Open Claude and click the 'Code' tab", file=sys.stderr)
        print("  2. Click 'New session', then 'Select folder', and choose:", file=sys.stderr)
        print(f"       {home}", file=sys.stderr)
        print("  3. Start talking. It loads its memory and disciplines from there.", file=sys.stderr)
        print(f'(Or from a terminal, if you have the CLI: cd "{home}" && claude)', file=sys.stderr)
    if "codex" in harnesses:
        print("To talk to it in Codex:", file=sys.stderr)
        print("  1. Open the Codex app (or a terminal with the codex CLI installed)", file=sys.stderr)
        print("  2. Open this folder as the project:", file=sys.stderr)
        print(f"       {home}", file=sys.stderr)
        print("  3. If Codex asks whether to trust the folder, say yes: it is your AI's own home.", file=sys.stderr)
        print(f'(Or from a terminal: cd "{home}" && codex)', file=sys.stderr)
    if both:
        print("Both doors read and write the SAME memory, so nothing forks whichever you open.", file=sys.stderr)


def _ensure_capability_entries(cfg) -> list:
    """Copy the shipped recipe for each configured capability into the vault
    once (`vault/reference/capabilities/<slug>.md`). The manual points at these
    paths, so `genesis verify` catches a slug with no file. The AI may annotate
    its copy (a standing rule the person gave, a wired tool); the shipped copy
    is never overwritten on a re-run, for the same reason the question bank is
    not. Returns the paths that exist afterwards."""
    from .seed import clean_capabilities
    src_dir = _P(__file__).with_name("resources") / "capabilities"
    out = []
    for slug in clean_capabilities(cfg.capabilities):
        src = src_dir / f"{slug}.md"
        dst = cfg.vault_dir / "reference" / "capabilities" / f"{slug}.md"
        if not dst.exists() and src.is_file():
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        if dst.exists():
            out.append(dst)
    return out


def _ensure_services(cfg) -> list:
    """The services loop's files, copied once and never overwritten: the ledger
    the AI keeps of what the person uses (always), and a walkthrough for each
    configured service. The manual points at these paths; `genesis verify`
    catches a pointer with no file."""
    from .seed import clean_services
    src_dir = _P(__file__).with_name("resources") / "services"
    dst_dir = cfg.vault_dir / "reference" / "services"
    out = []
    pairs = [("ledger.md", dst_dir / "ledger.md"), ("connecting.md", dst_dir / "connecting.md")]
    pairs += [(f"{slug}.md", dst_dir / f"{slug}.md") for slug in clean_services(cfg.services)]
    for name, dst in pairs:
        src = src_dir / name
        if not dst.exists() and src.is_file():
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        if dst.exists():
            out.append(dst)
    return out


def cmd_services(args) -> int:
    """List, add, or remove the online services this AI helps manage, copy the
    walkthrough for each, and re-render every wired door (a service can bring an
    MCP server with it, so the doors must be re-wired, not just the manual)."""
    from .seed import SERVICES, clean_services
    cfg = cfgmod.load()
    current = clean_services(cfg.services)
    changed = False
    for slug in (getattr(args, "add", None) or []):
        if slug not in SERVICES:
            print(f"no walkthrough for '{slug}' yet. Known: {', '.join(SERVICES)}. "
                  "Use the generic one at reference/services/connecting.md and note it in the ledger.",
                  file=sys.stderr)
            return 2
        if slug not in current:
            current.append(slug)
            changed = True
    for slug in (getattr(args, "remove", None) or []):
        if slug in current:
            current.remove(slug)
            changed = True
    if changed:
        cfgmod.update_fields(cfg, services=current or None)
        cfg = cfgmod.load()
        _ensure_services(cfg)
        _rerender_doors(cfg)
    if current:
        for slug in current:
            print(f"  {slug}: {cfg.vault_dir / 'reference' / 'services' / (slug + '.md')}")
    else:
        print("no services configured. Known walkthroughs: " + ", ".join(SERVICES))
    return 0


def cmd_capabilities(args) -> int:
    """List, add, or remove the domains this AI helps with, then re-render every
    wired door so the manual and the config never disagree."""
    from .seed import CAPABILITIES, clean_capabilities
    cfg = cfgmod.load()
    current = clean_capabilities(cfg.capabilities)
    changed = False
    for slug in (getattr(args, "add", None) or []):
        if slug not in CAPABILITIES:
            print(f"unknown capability '{slug}'. Known: {', '.join(CAPABILITIES)}", file=sys.stderr)
            return 2
        if slug not in current:
            current.append(slug)
            changed = True
    for slug in (getattr(args, "remove", None) or []):
        if slug in current:
            current.remove(slug)
            changed = True
    if changed:
        cfgmod.update_fields(cfg, capabilities=current or None)
        cfg = cfgmod.load()
        _ensure_capability_entries(cfg)
        _rerender_doors(cfg)
    if current:
        for slug in current:
            print(f"  {slug}: {cfg.vault_dir / 'reference' / 'capabilities' / (slug + '.md')}")
    else:
        print("no capabilities configured. Known: " + ", ".join(CAPABILITIES))
    return 0


def _rerender_doors(cfg) -> None:
    """Re-render CLAUDE.md / AGENTS.md for every wired harness (compile, don't fork)."""
    exe = _genesis_exe()
    home = _P.home() / "My AI"
    if not home.exists():
        return
    if "claude-code" in (cfg.harnesses or []):
        from . import claude_wire
        claude_wire.wire(cfg, exe, scope="project", home_dir=home)
    if "codex" in (cfg.harnesses or []):
        from . import codex_wire
        codex_wire.wire(cfg, exe, home_dir=home)


def _ensure_question_bank(cfg) -> _P:
    """Copy the shipped question bank into the vault once. The AI edits its copy."""
    src = _P(__file__).with_name("resources") / "relationship_questions.md"
    dst = cfg.vault_dir / "reference" / "relationship-questions.md"
    if not dst.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return dst


def _verify_vault(cfg) -> tuple:
    """Resolve every reference the vault makes, and say what is broken.

    Returns (ok, lines). Two link kinds, because they rot differently:
    `[[wikilinks]]`, which are notes to a future writer, and bare FILE PATHS,
    which are instructions to running code. A dead path is the more dangerous of
    the two: it produces a file-not-found that swallowed error handling turns
    into silence. That is exactly how an authored persona doc pointing at
    `relationship_questions.md`, in a vault that had slugged it to
    `relationship-questions.md`, killed a get-to-know-you drip for five days.
    """
    from genesis_memory import Graph, Vault, filerefs, selflint

    lines = []
    ok = True

    if not cfg.vault_dir.is_dir():
        return False, [f"no vault at {cfg.vault_dir}. Run `genesis init` first."]

    failed = []
    refs = filerefs.lint(cfg.vault_dir)
    lines.append(filerefs.render(refs))
    if refs["missing"] or refs["drift"]:
        ok = False
        failed.append("dead file references")

    # Does any document break a rule it declares about itself? A persona file is
    # the one place a vault states in plain language how its subject writes, and a
    # file that breaks its own rule in its own title reads, to the AI booting from
    # it, as permission. Encoding findings are reported but never fatal: a vault
    # may legitimately hold other languages, and refusing those would be a worse
    # bug than the mojibake this catches.
    self_r = selflint.lint_vault(cfg.vault_dir)
    if self_r["violations"] or self_r["non_ascii"]:
        lines.append("")
        lines.append(selflint.render(self_r))
    else:
        lines.append("")
        lines.append(f"self-consistency: {self_r['docs']} documents, none break a rule they declare")
    if self_r["violations"]:
        ok = False
        failed.append("documents breaking their own rules")

    try:
        g = Graph.from_vault(Vault(cfg.vault_dir))
        r = g.lint()
        lines.append("")
        lines.append(
            f"memory links: {r['nodes']} facts, {r['edges']} links, {r['dangling']} dangling "
            f"({len(r['drift'])} name-drift, {len(r['missing'])} never written)"
        )
        # Dangling wikilinks are NOT a failure. A [[link]] to an unwritten fact is
        # a legitimate write-me marker, and the reference companion carries dozens
        # on purpose. Reported, never fatal: a check that cries wolf on healthy
        # state gets ignored, and then it is not a check.
        if r["drift"]:
            lines.append("  name-drift worth fixing:")
            lines += [f"    [[{t}]] x{n} -> likely {gsn}" for t, n, gsn in r["drift"]]
    except Exception as e:  # a link lint must never be the thing that fails setup
        lines.append(f"\nmemory links: could not check ({e})")

    if failed:
        # Name what failed. A verdict that says "problems found" for three
        # different failure kinds makes the reader open the whole report to learn
        # which one, every time, and the reports people must fully read are the
        # reports people stop reading.
        lines.append("")
        lines.append("FAILING: " + ", ".join(failed))
    return ok, lines


def cmd_reach(args) -> int:
    """Can what is stored actually be FOUND? A different question from whether
    it is saved, and the one that usually goes unmeasured."""
    from genesis_memory import Vault, reachability

    cfg = cfgmod.load()
    if not cfg.vault_dir.is_dir():
        print(f"no vault at {cfg.vault_dir}. Run `genesis init` first.", file=sys.stderr)
        return 1
    bad = []
    facts = list(Vault(cfg.vault_dir).iter_facts(
        on_error=lambda p, e: bad.append(f"{p.name}: {e}")))
    r = reachability.report(facts, unreadable=bad,
                            chunk_tokens=getattr(args, "window", None)
                            or reachability.DEFAULT_CHUNK_TOKENS)
    print(reachability.render(r))
    # This instrument MEASURES; it does not grade. A reachability score is a
    # judgment about writing, and a build that fails on one teaches people to
    # write for the metric. A hard budget overflow is not a judgment, so that
    # one, and only that one, is an error.
    return 1 if r["index_over_budget"] else 0


def cmd_wire_codex(args) -> int:
    """Mode B, second door: write AGENTS.md + .codex/hooks.json into the AI's home
    and a trust entry into the user's Codex config. Idempotent."""
    from . import codex_wire
    cfg = cfgmod.load()
    home = _P(args.dir).expanduser() if getattr(args, "dir", None) else None
    out = codex_wire.wire(cfg, _genesis_exe(), home_dir=home)
    if "codex" not in cfg.harnesses:
        cfgmod.update_fields(cfg, harnesses=cfg.harnesses + ["codex"])
    print("Codex wired as a Genesis frontend:", file=sys.stderr)
    print(f"  AGENTS.md:  {out['agents_md']}", file=sys.stderr)
    print(f"  hooks:      {out['hooks']}  (SessionStart boot ritual, UserPromptSubmit re-anchor, Stop craft gate)", file=sys.stderr)
    print(f"  trust:      {out['config_toml']}  (marked block; project config loads only when trusted)", file=sys.stderr)
    print(f'Open it: cd "{out["launch_dir"]}" && codex', file=sys.stderr)
    return 0


def cmd_name(args) -> int:
    """Record the AI's name. Either party may run this: the person choosing a name,
    or the AI itself once one arrives. It is the only identity field config holds."""
    cfg = cfgmod.load()
    name = (args.name or "").strip()
    if not name:
        print("usage: genesis name <the name>", file=sys.stderr)
        return 1
    cfgmod.update_fields(cfg, name=name[:60])
    cfg.name = name[:60]
    # Re-render every wired door so the manual reassembles under the name next session.
    _rerender_doors(cfg)
    print(f"named: {cfg.name}", file=sys.stderr)
    return 0


def cmd_friction(args) -> int:
    """The craft loop's write path: record friction, an explicit none, a route, or a score."""
    from . import friction as fr
    cfg = cfgmod.load()
    if getattr(args, "none", False):
        fr.append_none(cfg.root)
        print("recorded: nothing this session (an honest zero)", file=sys.stderr)
        return 0
    if getattr(args, "route", None) is not None:
        idx, dest = args.route
        ok = fr.route(cfg.root, int(idx), dest)
        print(f"routed #{idx} -> {dest}" if ok else f"could not route #{idx} to {dest!r}", file=sys.stderr)
        return 0 if ok else 1
    if getattr(args, "won", None) is not None:
        ok = fr.score(cfg.root, int(args.won), True)
        print(f"scored #{args.won} won" if ok else f"no entry #{args.won}", file=sys.stderr)
        return 0 if ok else 1
    if getattr(args, "lost", None) is not None:
        ok = fr.score(cfg.root, int(args.lost), False)
        print(f"scored #{args.lost} not won" if ok else f"no entry #{args.lost}", file=sys.stderr)
        return 0 if ok else 1
    if getattr(args, "list", False):
        for i, r in enumerate(fr.load_queue(cfg.root)):
            if r.get("none"):
                print(f"#{i}  (none)  {r.get('when','')[:16]}")
            else:
                print(f"#{i}  [{r.get('kind')}] {r['text'][:90]}  -> {r.get('destination') or 'pending'}"
                      f"  won={r.get('won')}")
        s = fr.stats(cfg.root)
        print(f"{s['entries']} entries, {s['explicit_none']} none, {s['routed']} routed, {s['won']} won")
        jw = fr.journaling_warning(cfg.root)
        if jw:
            print("WARNING: " + jw)
        return 0
    text = (getattr(args, "text", None) or "").strip()
    if not text:
        print("usage: genesis friction \"<what happened>\" --kind gap|bug|tooling [--trigger ..] [--win ..] [--mitigation ..]\n"
              "       genesis friction --none | --list | --route N memory|rule|tool | --won N | --lost N", file=sys.stderr)
        return 1
    ok = fr.append_friction(cfg.root, text, kind=args.kind, mitigation=args.mitigation or "",
                            trigger=args.trigger or "", win=args.win or "", project=args.project or "")
    print("friction recorded (routed at the next dream)" if ok else "not recorded: empty text or bad kind", file=sys.stderr)
    return 0 if ok else 1


def cmd_craft_gate(args) -> int:
    """The Stop hook: once per session, if nothing was recorded in the friction queue
    since the session began, ask (exit 2 + stderr, which the harness feeds back to
    the AI). A second call in the same session passes, so the gate can never
    trap an AI that honestly answered. Never crashes: a broken gate must not
    block a session end."""
    import json as _json
    from datetime import datetime as _dt
    from . import friction as fr
    try:
        cfg = cfgmod.load()
        root = cfg.root
        # Session start = the last time the boot hook fired (primary evidence, not a
        # self-report). Fall back to "first time this gate ran" for homes never
        # booted through a hook.
        start = None
        log = root / "boot-context.log"
        if log.is_file():
            for ln in reversed(log.read_text(encoding="utf-8", errors="replace").splitlines()):
                if "source=hook" in ln:
                    try:
                        start = _dt.fromisoformat(ln.split()[0])
                    except Exception:
                        start = None
                    break
        stp = root / "craft_gate_state.json"
        st = {}
        if stp.is_file():
            try:
                st = _json.loads(stp.read_text(encoding="utf-8"))
            except Exception:
                st = {}
        if start is None:
            if st.get("fallback_start"):
                start = _dt.fromisoformat(st["fallback_start"])
            else:
                start = _dt.now()
                st["fallback_start"] = start.isoformat()
        key = start.isoformat()
        last = fr.last_entry_time(root)
        if last is not None and last >= start:
            return 0  # answered this session, either way
        if st.get("asked_for") == key:
            return 0  # already asked once this session; never trap
        st["asked_for"] = key
        stp.write_text(_json.dumps(st), encoding="utf-8")
        print(
            "CRAFT loop check, before you end: did you have to go FIND something that should have "
            "been in front of you, make a preventable mistake, or repeat a manual dance a tool should "
            "collapse? If yes, record it now: `genesis friction \"<what>\" --kind gap|bug|tooling "
            "--trigger \"next time I'm doing X\" --win \"I'll have avoided Y\"`. If genuinely nothing, "
            "record the explicit zero: `genesis friction --none`. Do NOT invent filler to satisfy this. "
            "Then end the turn.",
            file=sys.stderr,
        )
        return 2
    except Exception:
        return 0


def cmd_reanchor(args) -> int:
    """The UserPromptSubmit hook: count the prompt, and every N prompts print the
    compact identity block back into context. Never crashes, never blocks."""
    from . import reanchor as ra
    try:
        cfg = cfgmod.load()
        if ra.tick(cfg.root):
            print(ra.block(cfg))
    except Exception:
        pass
    return 0


def cmd_import(args) -> int:
    """Pre-seed the vault from a project's `docs/agent-seed/` (or any folder of
    fact files). Soul facts are refused: a seed pack cannot author a self."""
    from .importer import import_pack
    cfg = cfgmod.load()
    if cfg.engine_trains:
        print("import refused: this engine may train on your memory, so the vault is paused "
              "(connect a private engine first).", file=sys.stderr)
        return 1
    notes = []
    allow_soul = bool(getattr(args, "allow_soul", False))
    if allow_soul:
        # The owner-authored exception, taken on purpose and said out loud. A
        # project seed can never install a self; the PERSON who owns this home
        # can offer one as a footing. The manual tells the AI to hold it loosely.
        print("importing soul facts too: an owner-authored footing, on your say-so. "
              "Your AI will read them as an offer, not a script.", file=sys.stderr)
    out = import_pack(cfg.vault_dir, _P(args.path).expanduser(), allow_soul=allow_soul,
                      warn=notes.append)
    for w in out["written"]:
        print(f"  imported {w}", file=sys.stderr)
    for name, why in out["skipped"]:
        print(f"  skipped {name}: {why}", file=sys.stderr)
    for n in notes:
        print(f"  note: {n}", file=sys.stderr)
    print(f"imported {len(out['written'])} fact(s), skipped {len(out['skipped'])}", file=sys.stderr)
    return 0 if out["written"] or not out["skipped"] else 1


def cmd_verify(args) -> int:
    """Does everything this vault points at exist, and does it obey its own rules?"""
    cfg = cfgmod.load()
    ok, lines = _verify_vault(cfg)
    print(f"vault: {cfg.vault_dir}")
    for ln in lines:
        print(ln)
    print()
    print("verify:", "PASS" if ok else "PROBLEMS FOUND")
    return 0 if ok else 1


def cmd_health(args) -> int:
    """Is every loop that maintains this AI actually firing?"""
    import json as _json

    from . import mechanism_health as mh

    cfg = cfgmod.load()
    snap = mh.snapshot(cfg)
    if getattr(args, "json", False):
        print(_json.dumps(snap, indent=2))
    else:
        print(mh.render(snap))
    if getattr(args, "write", False):
        path = mh.write_snapshot(cfg)
        print(f"\nwrote {path}", file=sys.stderr)
    # Only failed and stale exit nonzero. never_fired is the correct state of a
    # fresh install, and a health check that goes red on a brand new machine is
    # a check the person learns to ignore before it ever means anything.
    bad = [m for m in snap["mechanisms"] if m["status"] in ("failed", "stale")]
    return 1 if bad else 0


def cmd_setup_daemon(args) -> int:
    """Schedule the hourly heartbeat (dream + learn) for the current OS:
    launchd (macOS), Task Scheduler (Windows), or cron (Linux)."""
    from .scheduler import get_scheduler

    cfg = cfgmod.load()
    st = get_scheduler(cfg.root).install()
    if st.wrapper:
        print(f"wrapper: {st.wrapper}", file=sys.stderr)
    print(f"scheduler: {st.detail}", file=sys.stderr)
    if st.registered:
        print("heartbeat scheduled hourly (dream + learn, each once per day)", file=sys.stderr)
        return 0
    print("could not register the OS job; the heartbeat can still be run manually: genesis heartbeat", file=sys.stderr)
    return 1


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="genesis", description="Genesis AI control surface")
    p.add_argument("--version", action="version", version="genesis-core " + __import__("genesis_core").__version__)
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("status", help="memory health at a glance").set_defaults(func=cmd_status)
    doctor_p = sub.add_parser("doctor", help="check engine + home are healthy (does a live 1-token call)")
    doctor_p.add_argument("--emptiness", action="store_true", help="CI gate: the package ships zero soul content (invariant 1)")
    doctor_p.add_argument("--path", default=None, help="path to scan for --emptiness (default: current dir)")
    doctor_p.set_defaults(func=cmd_doctor)
    sub.add_parser("chat", help="talk to your AI (reads lines from stdin)").set_defaults(func=cmd_chat)
    sub.add_parser(
        "install",
        help="guided setup: your AI walks you through getting started",
    ).set_defaults(func=cmd_install)
    dream_p = sub.add_parser("dream", help="run the inward reflection cycle (daykey-gated; safe to call hourly)")
    dream_p.add_argument("--force", action="store_true", help="run even if already dreamed today")
    dream_p.set_defaults(func=cmd_dream)
    sub.add_parser(
        "learn",
        help="run one outward cycle: pursue a thread you care about and bring back a finding",
    ).set_defaults(func=cmd_learn)
    sub.add_parser(
        "onboard",
        help="run the adaptive interview; configures your AI from your own answers",
    ).set_defaults(func=cmd_onboard)
    init_p = sub.add_parser(
        "init",
        help="stand up your AI on this machine: vault + tuning + scheduled loops",
    )
    init_p.add_argument(
        "--seed", default=None,
        help="apply a web-onboarding seed: a base64 blob, a file path, or '-' for stdin "
             "(also read from the GENESIS_SEED env var)",
    )
    init_p.add_argument(
        "--mode", choices=["agent", "claude-code", "codex"], default="agent",
        help="agent (Mode A: Genesis runs the loop on your engine), claude-code "
             "(Mode B: Claude Code is the brain, Genesis the memory), or codex "
             "(Mode B via OpenAI Codex); a seed may add the other door too",
    )
    init_p.set_defaults(func=cmd_init)
    sub.add_parser(
        "heartbeat",
        help="run the due maintenance loops (dream + learn); used by the scheduler",
    ).set_defaults(func=cmd_heartbeat)
    rec_p = sub.add_parser("recall", help="look up a saved fact by id or keyword (the read path)")
    rec_p.add_argument("--id", default=None, help="exact fact id, e.g. dog-vin")
    rec_p.add_argument("--query", default=None, help="keyword to match against descriptions and bodies")
    rec_p.set_defaults(func=cmd_recall)

    rem_p = sub.add_parser("remember", help="write one durable fact to the vault (the blessed write path)")
    rem_p.add_argument("--kind", required=True, choices=["user", "feedback", "project", "reference", "soul"])
    rem_p.add_argument("--id", required=True, help="a lowercase-hyphen slug, e.g. dog-vin")
    rem_p.add_argument("--desc", required=True, help="one line; this is what shows in the index")
    rem_p.add_argument("--body", default="", help="optional longer detail")
    rem_p.set_defaults(func=cmd_remember)
    bc_p = sub.add_parser(
        "boot-context",
        help="print the boot ritual (index + continuity + clock) for a SessionStart hook",
    )
    bc_p.add_argument("--hook", action="store_true", help="mark this as the SessionStart hook invocation (for diagnostics)")
    bc_p.set_defaults(func=cmd_boot_context)
    sub.add_parser(
        "seed-mode",
        help="print the runtime mode named by GENESIS_SEED (agent|claude-code|codex); used by the installer",
    ).set_defaults(func=cmd_seed_mode)
    wc_p = sub.add_parser(
        "wire-codex",
        help="Mode B: wire OpenAI Codex to run as a Genesis frontend (AGENTS.md + hooks + trust)",
    )
    wc_p.add_argument("--dir", default=None, help="the AI's home folder (default: ~/My AI)")
    wc_p.set_defaults(func=cmd_wire_codex)
    name_p = sub.add_parser("name", help="record the AI's name (the person's choice, or its own)")
    name_p.add_argument("name", nargs="?", default="", help="the name")
    name_p.set_defaults(func=cmd_name)
    fr_p = sub.add_parser("friction", help="the craft loop: record friction, an explicit none, a route, or a score")
    fr_p.add_argument("text", nargs="?", default="", help="what happened, in your own words")
    fr_p.add_argument("--kind", choices=["gap", "bug", "tooling"], default="gap")
    fr_p.add_argument("--trigger", default="", help="next time I'm doing X")
    fr_p.add_argument("--win", default="", help="I'll have avoided Y")
    fr_p.add_argument("--mitigation", default="", help="the fix, if you have one")
    fr_p.add_argument("--project", default="", help="optional project slug")
    fr_p.add_argument("--none", action="store_true", help="record the explicit zero for this session")
    fr_p.add_argument("--list", action="store_true", help="show the queue and its stats")
    fr_p.add_argument("--route", nargs=2, metavar=("N", "DEST"), default=None,
                      help="route entry N to memory|rule|tool")
    fr_p.add_argument("--won", type=int, default=None, metavar="N", help="score entry N as won")
    fr_p.add_argument("--lost", type=int, default=None, metavar="N", help="score entry N as not won")
    fr_p.set_defaults(func=cmd_friction)
    cg_p = sub.add_parser("craft-gate", help="Stop hook: ask once per session if no friction entry was recorded")
    cg_p.add_argument("--hook", action="store_true", help="mark this as the hook invocation")
    cg_p.set_defaults(func=cmd_craft_gate)
    ra_p = sub.add_parser("reanchor", help="UserPromptSubmit hook: re-deliver the register every N prompts")
    ra_p.add_argument("--hook", action="store_true", help="mark this as the hook invocation")
    ra_p.set_defaults(func=cmd_reanchor)
    im_p = sub.add_parser("import", help="pre-seed the vault from a folder of fact files (a project's docs/agent-seed)")
    im_p.add_argument("path", help="folder of *.md fact files")
    im_p.add_argument("--allow-soul", action="store_true",
                      help="also import `kind: soul` facts: the owner-authored footing you wrote for YOUR AI on purpose (a project seed never gets this)")
    im_p.set_defaults(func=cmd_import)
    cap_p = sub.add_parser("capabilities", help="list, add, or remove the domains this AI helps with (website, social, calendar, email, finances)")
    cap_p.add_argument("--add", action="append", metavar="SLUG", help="add a capability (repeatable)")
    cap_p.add_argument("--remove", action="append", metavar="SLUG", help="remove a capability (repeatable)")
    cap_p.set_defaults(func=cmd_capabilities)
    svc_p = sub.add_parser("services", help="list, add, or remove the online services this AI helps manage (wix, ...)")
    svc_p.add_argument("--add", action="append", metavar="SLUG", help="add a service (repeatable)")
    svc_p.add_argument("--remove", action="append", metavar="SLUG", help="remove a service (repeatable)")
    svc_p.set_defaults(func=cmd_services)
    wire_p = sub.add_parser(
        "wire-claude",
        help="Mode B: wire Claude Code to run as a Genesis frontend (CLAUDE.md + boot hook)",
    )
    wire_p.add_argument("--scope", choices=["project", "user"], default="project",
                        help="project (a companion home dir, non-invasive) or user (everywhere)")
    wire_p.add_argument("--dir", default=None, help="companion home dir for project scope (default: the Genesis home)")
    wire_p.set_defaults(func=cmd_wire_claude)
    es_p = sub.add_parser("email-sponsor", help="email your sponsor for help when genuinely stuck")
    es_p.add_argument("subject", help="short subject line")
    es_p.add_argument("body", help="the message (summarize the problem; never paste private memory)")
    es_p.set_defaults(func=cmd_email_sponsor)
    sub.add_parser("check-mail", help="poll the sponsor inbox for replies (used by the 10-min schedule)").set_defaults(func=cmd_check_mail)
    sy_p = sub.add_parser("sylph", help="outward learning: research a thread you care about on the live web")
    sy_p.add_argument("--topic", default=None, help="research this specific topic (default: next from your interests)")
    sy_p.add_argument("--add", default=None, help="add a topic to your interests watch-list")
    sy_p.add_argument("--remove", default=None, help="stop tracking a topic")
    sy_p.add_argument("--promote", default=None, help="promote a finding (path or slug) into durable behavior-shaping memory")
    sy_p.add_argument("--list", action="store_true", help="list your interests")
    sy_p.add_argument("--suggest", action="store_true", help="suggest candidate interests from what you already know")
    sy_p.set_defaults(func=cmd_sylph)
    cap_p = sub.add_parser("capture", help="queue a soul-capture candidate (the dream adjudicates it)")
    cap_p.add_argument("text", help="the thing that struck you, in your own words")
    cap_p.add_argument("--why", default="", help="optional: which part of you it touches")
    cap_p.set_defaults(func=cmd_capture)
    sub.add_parser(
        "setup-daemon",
        help="schedule the hourly heartbeat: dream + learn (launchd/Task Scheduler/cron)",
    ).set_defaults(func=cmd_setup_daemon)
    sched_p = sub.add_parser(
        "schedule",
        help="inspect or control the heartbeat schedule: status/pause/resume/install/uninstall",
    )
    sched_p.add_argument(
        "action", nargs="?", default="status",
        choices=["status", "pause", "resume", "install", "uninstall", "install-mail", "uninstall-mail"],
        help="what to do (default: status)",
    )
    sched_p.set_defaults(func=cmd_schedule)
    # Convenience top-level aliases for the two most common verbs.
    pause_p = sub.add_parser("pause", help="pause the heartbeat (stays scheduled, does no work)")
    pause_p.set_defaults(func=lambda a: cmd_schedule(__import__("argparse").Namespace(action="pause")))
    resume_p = sub.add_parser("resume", help="resume a paused heartbeat")
    resume_p.set_defaults(func=lambda a: cmd_schedule(__import__("argparse").Namespace(action="resume")))
    reach_p = sub.add_parser(
        "reach",
        help="can what is stored be found? orphans, index budget, long documents",
    )
    reach_p.add_argument("--window", type=int, default=None,
                         help="tokens a semantic layer would see per chunk "
                              "(default: %d)" % 2048)
    reach_p.set_defaults(func=cmd_reach)
    health_p = sub.add_parser(
        "health",
        help="are the background loops actually firing? (evidence, not self-reports)",
    )
    health_p.add_argument("--json", action="store_true", help="machine-readable snapshot")
    health_p.add_argument("--write", action="store_true",
                          help="also save the snapshot to <root>/mechanism_health.json")
    health_p.set_defaults(func=cmd_health)
    sub.add_parser(
        "verify",
        help="check that every file and link the vault points at actually exists",
    ).set_defaults(func=cmd_verify)
    sub.add_parser(
        "create-launcher",
        help="create a double-clickable launcher on the Desktop (macOS)",
    ).set_defaults(func=cmd_create_launcher)

    args = p.parse_args(argv)
    if not getattr(args, "func", None):
        p.print_help()
        return 0
    try:
        return args.func(args)
    except cfgmod.HomeNotFound as e:
        # A plain-language stop, never a stack trace. The person who hits this is
        # likelier to be someone's parent on their first AI than a developer.
        print(str(e), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
