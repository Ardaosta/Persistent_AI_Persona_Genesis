"""The unified `genesis` command. Verbs: status, doctor, chat, install."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path as _P

from genesis_backend.seam import BackendError, Message
from genesis_memory import Vault, index as index_mod

from . import config as cfgmod


def cmd_status(args) -> int:
    from .dream import get_last_dream, today_key
    from .relational import RelationalProfile
    cfg = cfgmod.load()
    print(f"home: {cfg.root}")
    print(f"engine: {cfg.provider} ({cfg.model or 'default model'})")
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

    last = get_last_dream(cfg.root)
    if last is None:
        print("last dream: never")
    elif last[0] == today_key():
        print(f"last dream: today at {last[1][11:16]}")
    else:
        from datetime import date
        days_ago = (date.today() - date.fromisoformat(last[0])).days
        label = "yesterday" if days_ago == 1 else f"{days_ago} days ago"
        print(f"last dream: {label} ({last[0]})")
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
    print(f"home: {cfg.root}")
    print(f"  vault:   {cfg.vault_dir}  [{'exists' if cfg.vault_dir.exists() else 'not created yet'}]")
    print(f"  secrets: {cfg.secrets_dir}  (sibling of the vault, never a tool allow-root)")
    print(f"engine: {cfg.provider}  model={cfg.model or '(default)'}")

    key = cfg.load_key()
    if not key:
        print("  key: NOT FOUND, add it to the secrets file or the env var")
        healthy = False
    else:
        print(f"  key: present ({len(key)} chars; value never printed)")
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

    cfg = cfgmod.load()

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
    if captures:
        trigger = (
            "(dream cycle)\n\nNotes you flagged as possibly load-bearing since your last dream:\n"
            + format_for_dream(captures)
            + "\n\nAdjudicate each honestly. If one genuinely belongs to who you are, keep it: "
            "save a soul fact with the remember tool (kind='soul'), merging into an existing one "
            "where it fits. If it doesn't, let it go. The bar is high and letting most go is "
            "healthy. Then reflect briefly on what you kept and why."
        )
        print(f"[genesis dream] adjudicating {len(captures)} capture(s)", file=sys.stderr)
    else:
        trigger = "(dream cycle)"
        print("[genesis dream]", file=sys.stderr)

    reflection = sess.turn(trigger, on_tool=_on_tool_quiet, max_steps=8)

    if captures:
        archive_queue(cfg.root)  # processed; don't re-adjudicate next time

    entry = write_journal(cfg.journal_dir, reflection)
    # The dream is first-person becoming, append it verbatim to the continuity
    # thread (append-only, never rewritten). Distinct from the dated journal.
    from genesis_memory import Continuity
    Continuity(cfg.vault_dir).append(reflection)
    ts = mark_dream(cfg.root)
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
    from .interview import UserModel, finalize, next_question, should_stop

    cfg = cfgmod.load()
    cfg.vault_dir.mkdir(parents=True, exist_ok=True)
    print("Let's set up your AI. A few quick questions, type the number of your answer.\n", file=sys.stderr)

    model = UserModel()
    while not should_stop(model):
        q = next_question(model)
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
    path = Vault(cfg.vault_dir).write(fact)
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
    if not learned_today(cfg.root):
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

    cfg = cfgmod.load()

    # 1. the home: a private vault + its structure (the three tiers)
    cfg.vault_dir.mkdir(parents=True, exist_ok=True)
    for d in ("soul", "journal", "findings", "continuity"):  # continuity tier inside the vault
        (cfg.vault_dir / d).mkdir(exist_ok=True)
    cfg.perishable_dir.mkdir(parents=True, exist_ok=True)  # perishable tier, SIBLING of vault
    print(f"home ready: {cfg.root}", file=sys.stderr)

    # 2. tune it: a seed from the web wins; else the local interview; else keep.
    seed = None
    try:
        seed = seedmod.load_seed_arg(getattr(args, "seed", None), _os.environ.get("GENESIS_SEED"))
    except ValueError as e:
        print(f"ignoring bad seed: {e}", file=sys.stderr)
    if seed:
        _apply_seed(cfg, seed)
        cfg = cfgmod.load()
        a = seed.get("archetype") or {}
        if a:
            print(f"tuned from web onboarding: {a.get('relationship','?')}, {a.get('engagement','?')}, "
                  f"{a.get('scope','?')}, {a.get('modality','?')}", file=sys.stderr)
        else:
            print("tuned from web onboarding seed.", file=sys.stderr)
    elif not cfg.machinery:
        cmd_onboard(_ap.Namespace())  # interview is brain-free; fine before a key exists
        cfg = cfgmod.load()
    else:
        print("already tuned; keeping it.", file=sys.stderr)

    # The mode can come from the CLI flag or, for a web onboard, from the seed.
    mode = getattr(args, "mode", "agent") or "agent"
    if mode == "agent" and seed and seed.get("mode"):
        mode = seed["mode"]

    # Mode B: Claude Code is the brain (authed by the user's Claude subscription),
    # so there's no API key to fetch. Wire it up and point them at launching it.
    if mode in ("claude-code", "claude", "b"):
        from . import claude_wire
        # The folder the user picks in Claude Code's "Select folder" must be easy to
        # find: a clearly-named, VISIBLE folder, not a hidden dotfolder lost among
        # .claude/.genesis/.genesis-app. The vault stays at the root; CLAUDE.md
        # points at it by absolute path, so the home and the vault can differ.
        home = _P.home() / "My AI"
        home.mkdir(parents=True, exist_ok=True)
        claude_wire.wire(cfg, _genesis_exe(), scope="project", home_dir=home)
        print("\nMode B ready: Claude is your AI's brain, your vault is its memory.", file=sys.stderr)
        print("To talk to it in the Claude desktop app (no terminal needed):", file=sys.stderr)
        print("  1. Open Claude and click the 'Code' tab", file=sys.stderr)
        print("  2. Click 'New session', then 'Select folder', and choose:", file=sys.stderr)
        print(f"       {home}", file=sys.stderr)
        print("  3. Start talking. It loads its memory and disciplines from there.", file=sys.stderr)
        print(f'(Or from a terminal, if you have the CLI: cd "{home}" && claude)', file=sys.stderr)
        return 0

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

    print("\nDone. A private, tuned home on your machine, dreaming and learning on a schedule.", file=sys.stderr)
    print("Talk to it: genesis chat", file=sys.stderr)
    return 0


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
        "--mode", choices=["agent", "claude-code"], default="agent",
        help="agent (Mode A: Genesis runs the loop on your engine) or claude-code "
             "(Mode B: Claude Code is the brain, Genesis the memory)",
    )
    init_p.set_defaults(func=cmd_init)
    sub.add_parser(
        "heartbeat",
        help="run the due maintenance loops (dream + learn); used by the scheduler",
    ).set_defaults(func=cmd_heartbeat)
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
        help="print the runtime mode named by GENESIS_SEED (agent|claude-code); used by the installer",
    ).set_defaults(func=cmd_seed_mode)
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
    sub.add_parser(
        "create-launcher",
        help="create a double-clickable launcher on the Desktop (macOS)",
    ).set_defaults(func=cmd_create_launcher)

    args = p.parse_args(argv)
    if not getattr(args, "func", None):
        p.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
