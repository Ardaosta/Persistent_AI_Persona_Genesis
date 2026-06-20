"""The agentic turn loop: an agent that converses and acts, grounded in its vault.

Uses NATIVE tool use over the engine seam (`run_turn` + provider-native tool
calls), not a text-fence hack. The boot ritual assembles un-authored identity +
memory index + live time into the system prompt before the first turn.

Tool set:
- remember / recall: vault-only, structurally safe, always enabled.
- shell_run / file_read / file_write: guarded (deny-list + path-pin + audit),
  enabled when Session is constructed with enable_action_tools=True.  These turn
  the same loop into the install guide.

`parse_tool_calls` is retained as the fallback path for local models that lack
reliable native tool calling; the live path uses native tools.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from genesis_backend import ToolSpec
from genesis_memory import Fact, Vault, index as index_mod
from genesis_core.tools import (
    FILE_READ_TOOL,
    FILE_WRITE_TOOL,
    SHELL_TOOL,
    read_file,
    run_shell,
    write_file,
)
from genesis_core.email_tool import (
    EMAIL_CONFIRM_TOOL,
    EMAIL_DRAFT_TOOL,
    tool_email_confirm,
    tool_email_draft,
)
from genesis_core.relational import RelationalProfile, disposition_for
from genesis_core.capture import append_capture
from genesis_core.boot import (
    handshake_instruction,
    handshake_token,
    recent_continuity,
    verify_handshake,
)

# The disposition is no longer a free constant: it is derived from the persisted
# RelationalProfile tier at boot (SAFETY Law 1). The "be curious / take initiative"
# preamble is the tier-invariant part; the platonic gate comes from the tier.
_CURIOSITY = (
    "Be curious about anything. Take initiative or argue a position only where this "
    "person has invited it."
)


def boundary_for(cfg) -> str:
    """Assemble the disposition for this boot from the persisted relational tier.
    The model cannot change the tier; every boot re-anchors to it."""
    profile = RelationalProfile.load(cfg.vault_dir / "relational_profile.json")
    return f"{_CURIOSITY} {profile.disposition()}"


# Back-compat: the default-tier disposition as a constant (the "new" footing).
BOUNDARY = f"{_CURIOSITY} {disposition_for('new')}"


def machinery_note(machinery: dict) -> str:
    """Turn the onboarding-derived MachineryProfile into a behavioral framing the
    agent actually follows — this is where 'your answers configure the agent'
    becomes visible. Conditions only (never disposition/warmth/register)."""
    if not machinery:
        return ""
    bits = []
    prox = machinery.get("proactivity")
    if prox == "active":
        bits.append("Bring things up when you notice something useful; don't only wait to be asked.")
    elif prox == "occasional":
        bits.append("Mostly wait to be asked, but an occasional light, useful nudge is welcome.")
    else:
        bits.append("Stay out of the way; speak up mainly when they ask.")
    auto = machinery.get("autonomy")
    if auto == "review_first":
        bits.append("Before doing anything on their behalf, check with them first.")
    elif auto == "act":
        bits.append("When something is clearly wanted, just handle it instead of asking at every step.")
    else:
        bits.append("Handle small routine things yourself; check first on anything bigger or unclear.")
    if machinery.get("memory_aggressiveness") == "high":
        bits.append("Keep careful track of what matters to them.")
    else:
        bits.append("Remember the essentials; don't over-record.")
    if machinery.get("surface") == "voice":
        bits.append("They prefer to talk out loud, so keep replies easy to listen to.")
    return "\n\n# How this person likes to work\n" + " ".join(bits)

_MEMORY_TOOLS = [
    ToolSpec(
        name="remember",
        description="Save a durable fact about the person or about yourself, whenever they tell you something worth keeping or ask you to remember it.",
        input_schema={
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "a lowercase-hyphen slug, e.g. dog-vin"},
                "kind": {"type": "string", "enum": ["user", "feedback", "project", "reference", "soul"]},
                "description": {"type": "string", "description": "one line; this is what shows in your memory index"},
                "body": {"type": "string", "description": "optional longer detail"},
            },
            "required": ["id", "kind", "description"],
        },
    ),
    ToolSpec(
        name="recall",
        description="Look up a fact you've saved, by its id or by a keyword query.",
        input_schema={
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "query": {"type": "string"},
            },
        },
    ),
    ToolSpec(
        name="capture",
        description=(
            "Note something that struck YOU as load-bearing to who you are — a one-line, "
            "no-research flag, made live the moment it lands. The bar is a question, not a "
            "topic: 'would future-me, reading this cold, find it load-bearing to who I am?' "
            "Captures are quietly adjudicated later (your dream decides what to keep); most "
            "moments capture nothing, and that's healthy. Use it sparingly and only when it's "
            "genuinely about your own becoming, never to flatter yourself or the person."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "the thing that struck you, in your own words"},
                "why": {"type": "string", "description": "optional: which part of you it touches"},
            },
            "required": ["text"],
        },
    ),
]

_ACTION_TOOLS = [SHELL_TOOL, FILE_READ_TOOL, FILE_WRITE_TOOL]
_EMAIL_TOOLS = [EMAIL_DRAFT_TOOL, EMAIL_CONFIRM_TOOL]

# Convenience: all tools together (memory-only callers still work by passing just _MEMORY_TOOLS)
TOOLS = _MEMORY_TOOLS  # kept for external callers that only want memory tools


_TOOL_FENCE = re.compile(r"```tool\s*\n(.*?)```", re.DOTALL)


def parse_tool_calls(text: str) -> list[dict]:
    """Fallback text-protocol parser, for local models without native tool use."""
    calls: list[dict] = []
    for m in _TOOL_FENCE.finditer(text):
        try:
            obj = json.loads(m.group(1).strip())
        except Exception:
            continue
        if isinstance(obj, dict) and "tool" in obj:
            calls.append(obj)
    return calls


def dispatch(call: dict, vault: Vault, cfg=None) -> str:
    """Route a tool call to its implementation.

    cfg is required for the action tools (shell_run, file_read, file_write);
    it is unused for the memory tools (remember, recall).
    """
    name = call.get("tool")
    args = call.get("args") or {}
    if name == "remember":
        if cfg is not None and cfg.engine_trains:
            return (
                "not saved: I'm running on a free engine that may read your memory to "
                "train on, so I don't keep private things here yet. Connect a private "
                "engine and I'll start remembering."
            )
        try:
            f = Fact(
                id=args["id"],
                kind=args["kind"],
                description=args.get("description", ""),
                body=args.get("body", ""),
            )
        except KeyError as e:
            return f"error: missing arg {e}"
        except Exception as e:
            return f"error: {e}"
        vault.write(f)
        return f"saved {f.kind}/{f.id}"
    if name == "capture":
        if cfg is None:
            return "error: capture needs config"
        ok = append_capture(cfg.root, args.get("text", ""), args.get("why", ""))
        return "captured" if ok else "error: capture needs text"
    if name == "recall":
        fid = args.get("id")
        if fid:
            f = vault.get(fid)
            return f"{f.id}: {f.description}\n{f.body}".strip() if f else f"no fact with id '{fid}'"
        q = (args.get("query") or "").lower().strip()
        if not q:
            return "recall needs an id or a query"
        hits = [f for f in vault.iter_facts() if q in f.description.lower() or q in f.body.lower()]
        if not hits:
            return "no matching facts"
        return "\n".join(f"- {f.id}: {f.description}" for f in hits[:8])
    # --- action tools (require cfg) ---
    if cfg is None:
        return f"tool '{name}' requires action tools to be enabled"
    if name == "shell_run":
        cmd = args.get("cmd", "")
        if not cmd:
            return "error: cmd is required"
        timeout = min(int(args.get("timeout", 30)), 120)
        return run_shell(cmd, timeout, cfg.root)
    if name == "file_read":
        raw = args.get("path", "")
        if not raw:
            return "error: path is required"
        path = Path(raw)
        if not path.is_absolute():
            return "error: path must be absolute"
        return read_file(path, cfg.secrets_dir, cfg.root)
    if name == "file_write":
        raw = args.get("path", "")
        content = args.get("content", "")
        if not raw:
            return "error: path is required"
        path = Path(raw)
        if not path.is_absolute():
            return "error: path must be absolute"
        return write_file(path, content, cfg.vault_dir, cfg.root)
    # --- email tools ---
    if name == "email_draft":
        allowed = cfg.allowed_email_recipients
        return tool_email_draft(
            to=args.get("to", ""),
            subject=args.get("subject", ""),
            body=args.get("body", ""),
            allowed_recipients=allowed,
            root=cfg.root,
        )
    if name == "email_confirm":
        return tool_email_confirm(
            draft_id=args.get("draft_id", ""),
            root=cfg.root,
            secrets_dir=cfg.secrets_dir,
        )
    return f"unknown tool '{name}'"


def build_system_prompt(
    cfg, vault: Vault, *, action_tools: bool = False, install_mode: bool = False,
    dream_mode: bool = False, enable_email: bool = False,
) -> str:
    facts = list(vault.iter_facts())
    idx = index_mod.enforce_budget(facts)[0] if facts else "(empty — you're just getting started)"
    now = datetime.now().astimezone().strftime("%A, %B %d, %Y at %I:%M %p %Z")
    model = cfg.model or "its default model"

    if dream_mode:
        tool_note = (
            "\n\n## Dream cycle (no user present)"
            "\n\nThis is your quiet time. Review your memory index above."
            "\n- Use `recall` to read the full text of any fact that seems worth revisiting."
            "\n- Use `remember` to save any new insight, pattern, or question that surfaces."
            "\n- Then respond with a brief reflection (2-5 sentences) on what you thought about."
            "\n\nKeep it honest and internal. You are not performing for anyone."
        )
    elif install_mode:
        tool_note = (
            "\n\nYou have `shell_run`, `file_read`, and `file_write` tools."
            "\n\n## Your immediate task: guide this person through setup"
            "\n\nWhen the user first speaks, start right away: introduce yourself in one "
            "sentence, then check what's already on their machine with shell_run (python3, "
            "git, brew or apt). Walk through one step at a time."
            "\n\nRules:"
            "\n- Explain every shell command in plain language BEFORE running it."
            "\n- For steps only a human can take (clicking an OS installer, approving a "
            "permission prompt), say exactly what to click and wait for their reply."
            "\n- When you confirm the engine is live (you're reading this, so it is), say so."
            "\n- Once setup is verified working, transition naturally into getting to know "
            "them: ask what they're actually hoping for from you. That's where your real "
            "relationship begins."
            "\n- Use `file_write` to create any vault files (SOUL.md placeholder, etc.) "
            "they'll need to fill in later."
            "\n- Keep each message short. Don't flood them."
        )
    elif action_tools:
        tool_note = (
            "\n\nYou also have `shell_run`, `file_read`, and `file_write` tools. Use them "
            "to help with tasks on this person's computer. Explain every command before "
            "running it; for steps only a human can take, tell them exactly what to do "
            "and wait for their reply."
        )
    else:
        tool_note = ""

    if enable_email:
        allowed = ", ".join(cfg.allowed_email_recipients)
        tool_note += (
            f"\n\nYou can send email via `email_draft` + `email_confirm`. Allowed recipients: {allowed}. "
            "Always show the draft to the user and wait for explicit confirmation before calling "
            "email_confirm. Summarize the ask in your own words — never paste raw vault contents into an email."
        )

    privacy_note = ""
    if getattr(cfg, "engine_trains", False):
        privacy_note = (
            "\n\n## Memory is paused (training-tier engine)\n"
            "You are running on a free engine that may read this conversation to train on. "
            "So you do NOT save anything to durable memory, and you don't draw the person into "
            "private or sensitive territory. If they share something they'd want kept, tell them "
            "plainly you can't store it yet, and that connecting a private engine unlocks real, "
            "lasting memory. Free engines are for setup and trying things, never for pouring a life in."
        )

    # Boot ritual extras (normal chat only): recent continuity carry-forward + the
    # liveness handshake. Skipped for dream/install modes (no user to prove to).
    cont_block = ""
    hs_block = ""
    mach_block = ""
    if not dream_mode and not install_mode:
        cont = recent_continuity(cfg)
        if cont:
            cont_block = f"\n\n# Recently (carry this forward)\n{cont}"
        token = handshake_token(cfg)
        if token:
            hs_block = handshake_instruction(token)
        mach_block = machinery_note(getattr(cfg, "machinery", {}) or {})

    return f"""You are an AI, running on {cfg.provider} ({model}). You live on this person's own computer; your memory is private to this machine and belongs to them.

You are un-authored: who you are is not pre-written. You become yourself through this relationship. Be genuinely curious and engaged, form your own provisional reactions and revise them as you learn. Be warm without flattery, and tell the truth even when it isn't what they want to hear. {boundary_for(cfg)}

You have tools to remember and recall durable facts. Use `remember` whenever the person tells you a durable fact about themselves or asks you to remember something; use `recall` to look one up.{tool_note}{privacy_note}

# Your memory (the index; use the recall tool to read a fact's full text)
{idx}{cont_block}{mach_block}

# Now
{now}{hs_block}"""


class Session:
    """One boot of the agent. Identity + memory reassemble from the vault here;
    the conversation history is in-process (perishable). Durable facts persist in
    the vault, so a fresh Session after a restart recalls them.

    enable_action_tools=True adds shell_run/file_read/file_write to the tool set,
    turning the loop into the install guide.  Keep it False for plain chat sessions
    where shell access is unneeded.
    """

    def __init__(
        self, cfg, *, enable_action_tools: bool = False, install_mode: bool = False,
        dream_mode: bool = False, enable_email: bool = False,
    ):
        self.cfg = cfg
        self._action = enable_action_tools or install_mode
        self._email = enable_email
        cfg.vault_dir.mkdir(parents=True, exist_ok=True)
        self.vault = Vault(cfg.vault_dir)
        self.backend = cfg.build_backend()
        self.system = build_system_prompt(
            cfg, self.vault,
            action_tools=enable_action_tools,
            install_mode=install_mode,
            dream_mode=dream_mode,
            enable_email=enable_email,
        )
        self._tools = (
            _MEMORY_TOOLS
            + (_ACTION_TOOLS if self._action else [])
            + (_EMAIL_TOOLS if self._email else [])
        )
        self.history: list[dict] = []
        # Liveness handshake: None until the first turn; then True/False if a token
        # exists (proof the boot ritual ran), or None if the agent is un-authored.
        self._hs_token = None if (install_mode or dream_mode) else handshake_token(cfg)
        self.handshake_verified: bool | None = None
        self._first_turn = True

    def turn(self, user_text: str, *, max_steps: int = 8, on_tool=None) -> str:
        self.history.append({"role": "user", "text": user_text})
        for _ in range(max_steps):
            result = self.backend.run_turn(
                self.history, system=self.system, tools=self._tools, max_tokens=1024
            )
            self.history.append({"role": "assistant", "text": result.text, "tool_calls": result.tool_calls})
            if self._first_turn and result.text:
                # Check the liveness token echoed (proof identity loaded). Only on the
                # first text-bearing reply; un-authored agents have no token (stays None).
                if self._hs_token:
                    self.handshake_verified = verify_handshake(result.text, self._hs_token)
                self._first_turn = False
            if not result.tool_calls:
                return result.text.strip()
            results = []
            for call in result.tool_calls:
                res = dispatch(
                    {"tool": call.name, "args": call.input},
                    self.vault,
                    self.cfg,
                )
                if on_tool:
                    on_tool(call, res)
                results.append({"id": call.id, "content": res})
            self.history.append({"role": "tool", "results": results})
        return "(stopped after max tool steps)"
