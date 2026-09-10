"""Resolve {home, engine, model, key} into a usable Backend.

Home layout (everything lives on the user's own machine):

    $GENESIS_ROOT/                 default: ~/.genesis
      vault/                       the memory (tools path-pin HERE, never the root)
      secrets/<provider>.key       mode 0600, OUTSIDE the vault so no tool allow-root reaches it
      config.json                  non-secret: provider + model

The secrets dir being a *sibling* of the vault (not inside it) is load-bearing:
the agent's file tools are rooted at vault/, so they structurally cannot read the
key, even though it's the agent's own uid.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from genesis_backend import (
    AnthropicBackend,
    ClaudeCLIBackend,
    GeminiBackend,
    OpenAIBackend,
    ResponsesBackend,
)

ANTHROPIC_DEFAULT_MODEL = "claude-sonnet-4-6"
GEMINI_DEFAULT_MODEL = "gemini-2.5-flash"

# Which env var holds the key, per provider. "openai-responses" is the same
# OpenAI key on the /v1/responses endpoint (required for gpt-5.x tool use, which
# chat/completions no longer supports).
_KEY_ENV = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "openai-responses": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
}

# Does the engine reserve the right to train on the user's data? Free Gemini does;
# the Anthropic/OpenAI APIs do not by default. Unknown providers fail CLOSED
# (assume training). A user on a paid/non-training tier can override in config.json
# with {"engine_trains": false}. This gates whether the agent will deepen into
# private memory (SAFETY #3 / review issue #1): never pour a life into an engine that
# will read the depth. claude-cli runs on a private subscription (no training tier),
# so it is non-training like the paid APIs.
_TRAINS_DEFAULT = {"anthropic": False, "openai": False, "openai-responses": False, "gemini": True, "claude-cli": False}


# A breadcrumb dropped inside a real home by `genesis init`. Primary evidence:
# it says this directory was deliberately provisioned, by whom and when, rather
# than manufactured by a bare command that happened to run with GENESIS_ROOT unset.
HOME_MARKER = ".genesis-home"

# The fallback home, used only when GENESIS_ROOT is unset AND it is already a real
# home (or we are explicitly allowed to create one). Never auto-created underneath
# a running agent: see resolve_root().
FALLBACK_HOME_NAME = ".genesis"


class HomeNotFound(RuntimeError):
    """No Genesis home to work in, and this command is not allowed to invent one.

    Raised instead of silently creating an empty ~/.genesis, which is how a live
    agent gets forked away from its own memory (KNOWN_ISSUES-silent-vault-fork).
    """


def default_root() -> Path:
    """The path a bare command resolves to. Pure: creates nothing, checks nothing."""
    env = os.environ.get("GENESIS_ROOT")
    return Path(env).expanduser() if env else Path.home() / FALLBACK_HOME_NAME


def is_provisioned(root: Path) -> bool:
    """Does this directory hold a real home, as opposed to being empty or absent?

    Three independent signals, any one of which is enough. The marker is the
    deliberate one; config.json and a non-empty vault cover homes provisioned
    before the marker existed, so an upgrade never looks like a missing home.
    """
    try:
        if (root / HOME_MARKER).is_file():
            return True
        if (root / "config.json").is_file():
            return True
        vault = root / "vault"
        if vault.is_dir() and any(vault.rglob("*.md")):
            return True
    except OSError:
        pass
    return False


def _candidate_homes() -> list:
    """Places a home plausibly lives on this machine.

    One level under the user's home directory plus the conventional names. Bounded
    and cheap (a single listdir). This exists to ANSWER "is there a real home
    somewhere else?" when a bare command is about to strand an agent in a new one.
    It is diagnostic only and never silently switches the active home. The real
    incident that motivated this is covered by construction: that home was an
    ordinary visible folder one level down, C:\\Users\\<user>\\<the AI's name>.
    """
    home = Path.home()
    cands = [home / FALLBACK_HOME_NAME, home / "Genesis", home / "My AI"]
    try:
        for child in home.iterdir():
            if not child.is_dir():
                continue
            # Hidden dirs are noise (caches, app support) apart from the fallback,
            # which is already first in the list.
            if child.name.startswith(".") and child.name != FALLBACK_HOME_NAME:
                continue
            cands.append(child)
    except OSError:
        pass
    seen, out = set(), []
    for c in cands:
        key = str(c)
        if key not in seen:
            seen.add(key)
            out.append(c)
    return out


def find_homes(exclude: Path | None = None) -> list:
    """Every provisioned home this machine can see, minus `exclude`."""
    ex = str(exclude.expanduser().resolve()) if exclude else None
    out = []
    for c in _candidate_homes():
        try:
            if ex and str(c.resolve()) == ex:
                continue
        except OSError:
            continue
        if is_provisioned(c):
            out.append(c)
    return out


def resolve_root(*, creating: bool = False) -> Path:
    """The active home, refusing to invent one under a command that should not.

    The bug this closes: a bare `genesis remember` run from the agent's own shell,
    with GENESIS_ROOT unset, used to mkdir a fresh empty ~/.genesis and start
    writing facts into it. In the field this forked a live AI away from its own
    memory for two days: it greeted its person by the wrong name, re-learned them
    from scratch, and stranded nine facts in the fork. Nothing notified anyone,
    because from inside the fork everything looked fine.

    So: an explicit GENESIS_ROOT always wins, an already-provisioned home is used,
    and otherwise only commands that are SUPPOSED to create a home (init, install,
    onboard) may proceed. Everything else fails loudly, names the env var, and
    points at any real home it can see.
    """
    root = default_root()
    if creating:
        return root

    pinned = os.environ.get("GENESIS_ROOT")
    if pinned:
        # Set, but pointing somewhere that is not a home. Trusting it blindly is
        # how the guard gets walked around through its own front door: a stale
        # pin (a moved folder, a cleaned-up temp path, a typo in a profile) would
        # otherwise be mkdir'd back into existence as a fresh empty vault, which
        # is the very fork this whole module exists to prevent. genesis-mcp has
        # validated its root since the day it was built; this is the CLI catching
        # up to it.
        if not is_provisioned(root):
            what = "does not exist" if not root.exists() else "is not an AI home"
            others = find_homes(exclude=root)
            lines = [
                f"GENESIS_ROOT points at {root}, which {what}.",
                "",
                "Refusing to build a new empty home there. If that path is stale, the memory",
                "you are looking for is somewhere else and creating this would hide it.",
            ]
            if others:
                lines += ["", "The home on this machine is:"] + [f"    {o}" for o in others]
            lines += ["", "To set one up at this exact path on purpose:", "    genesis init"]
            raise HomeNotFound("\n".join(lines))
        return root

    if is_provisioned(root):
        return root

    others = find_homes(exclude=root)
    lines = [
        f"No AI home found at {root}, and GENESIS_ROOT is not set.",
        "",
        "Refusing to create an empty one: a blank home looks like amnesia, not like",
        "an error, so this stops here instead of quietly starting over.",
    ]
    # Show the remediation for THIS os only. A macOS user handed a `setx` line
    # holding a POSIX path has been given a command that cannot work, and the
    # instinct that follows is to route around the guard rather than read it.
    def _pin_cmd(path) -> str:
        if os.name == "nt":
            return f'    setx GENESIS_ROOT "{path}"'
        return f'    export GENESIS_ROOT="{path}"'

    example = "C:\\path\\to\\the\\home" if os.name == "nt" else "/path/to/the/home"
    if others:
        lines += ["", "There is already a home on this machine:"]
        lines += [f"    {o}" for o in others]
        lines += ["", "Point at it before running this again:", _pin_cmd(others[0])]
    else:
        lines += [
            "",
            "If this machine has no AI yet, set one up:",
            "    genesis init",
            "",
            "If it does, and it lives somewhere else, point at it:",
            _pin_cmd(example),
        ]
    raise HomeNotFound("\n".join(lines))


def write_home_marker(root: Path) -> Path:
    """Drop the deliberate-provisioning breadcrumb. Idempotent: never overwrites an
    existing marker, because the ORIGINAL creation stamp is the useful one."""
    import socket
    from datetime import datetime

    path = root / HOME_MARKER
    if path.is_file():
        return path
    root.mkdir(parents=True, exist_ok=True)
    payload = {
        "created_at": datetime.now().astimezone().isoformat(),
        "host": socket.gethostname(),
        "path": str(root),
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def write_home_pointer(root: Path) -> tuple:
    """Make bare `genesis` calls resolve here FOREVER, not just in this shell.

    Fix 2 from the known-issues doc. The field fork happened because the home was
    pinned in the heartbeat script and a SessionStart hook and nowhere else, so every
    OTHER invocation (the agent's own shell, a terminal the user opened) resolved
    somewhere else. A durable pointer is what makes them all agree.

    Returns (ok, human_readable_detail). Never raises: failing to persist the
    pointer must not fail the setup that was otherwise fine.
    """
    root = Path(root).expanduser()
    if os.name == "nt":
        import subprocess
        try:
            subprocess.run(["setx", "GENESIS_ROOT", str(root)],
                           check=True, capture_output=True, timeout=30)
            return True, "GENESIS_ROOT set for your Windows account (new terminals pick it up)"
        except Exception as e:  # noqa: BLE001 - reported, never fatal
            return False, f"could not set GENESIS_ROOT: {e}"

    shell = os.environ.get("SHELL", "")
    if "zsh" in shell:
        profile = Path.home() / ".zshrc"
    elif "bash" in shell:
        profile = Path.home() / ".bashrc"
    else:
        profile = Path.home() / ".profile"

    begin = "# >>> genesis home >>>"
    end = "# <<< genesis home <<<"
    block = f'{begin}\nexport GENESIS_ROOT="{root}"\n{end}\n'
    try:
        existing = profile.read_text(encoding="utf-8") if profile.is_file() else ""
        if begin in existing:
            head, _, rest = existing.partition(begin)
            _, _, tail = rest.partition(end)
            new = head + block + tail.lstrip("\n")
        else:
            sep = "" if (not existing or existing.endswith("\n")) else "\n"
            new = existing + sep + "\n" + block
        profile.write_text(new, encoding="utf-8")
        return True, f"GENESIS_ROOT pinned in {profile} (new terminals pick it up)"
    except OSError as e:
        return False, f"could not write {profile}: {e}"


# The root sponsor (SOVEREIGNTY.md "Help: the sponsor graph"): the fallback
# contact an agent can email when it's stuck and onboarding captured no personal
# sponsor. EMPTY here so the private dev tree ships nothing personal; the public
# distribution build sets this to a dedicated, non-personal project/support
# address. A per-user sponsor (captured at onboarding) always overrides it.
DEFAULT_SPONSOR_EMAIL = "AIPersonaGenesis@protonmail.com"

_DEFAULT_EMAIL_RECIPIENTS = [DEFAULT_SPONSOR_EMAIL] if DEFAULT_SPONSOR_EMAIL else []


@dataclass
class GenesisConfig:
    root: Path
    provider: str = "anthropic"  # "anthropic" | "openai" | "gemini"
    model: str | None = None
    allowed_email_recipients: list = None  # defaults to _DEFAULT_EMAIL_RECIPIENTS
    trains: bool | None = None  # None → derive from provider (fail-closed)
    machinery: dict = None  # onboarding-derived MachineryProfile (proactivity/autonomy/memory/surface)
    sponsor_sender: str | None = None  # the email account the agent sends sponsor mail FROM
    # The four seed-time conditions added 2026-09-10. None of them author a self:
    # a name is the person's choice (or the AI's own, recorded later), the project
    # is a pointer, the drip is an opt-in, and harnesses are which doors are wired.
    name: str | None = None            # the AI's name, if one has been chosen
    project_repo: str | None = None    # a repository this AI is joining (URL or path)
    drip: bool = False                 # the getting-to-know-you question drip is on
    harnesses: list = None             # Mode-B doors wired into this home: claude-code, codex

    def __post_init__(self):
        if self.allowed_email_recipients is None:
            self.allowed_email_recipients = list(_DEFAULT_EMAIL_RECIPIENTS)
        if self.machinery is None:
            self.machinery = {}
        if self.harnesses is None:
            self.harnesses = []

    @property
    def engine_trains(self) -> bool:
        """Whether the current engine may train on the user's data (fail-closed)."""
        if self.trains is not None:
            return self.trains
        return _TRAINS_DEFAULT.get(self.provider, True)

    @property
    def vault_dir(self) -> Path:
        return self.root / "vault"

    @property
    def secrets_dir(self) -> Path:
        return self.root / "secrets"  # sibling of vault, never a tool allow-root

    @property
    def perishable_dir(self) -> Path:
        # SIBLING of the vault: working-state that must never leak into durable memory
        return self.root / "perishable"

    @property
    def continuity_dir(self) -> Path:
        return self.vault_dir / "continuity"  # inside vault (owned), not a Fact kind

    @property
    def daykeys_dir(self) -> Path:
        return self.root / "daykeys"  # operational; one file per day the dream ran

    @property
    def journal_dir(self) -> Path:
        return self.vault_dir / "journal"  # inside vault so the agent can read/recall entries

    @property
    def findings_dir(self) -> Path:
        return self.vault_dir / "findings"  # the OUTWARD loop's surfaced findings

    @property
    def config_path(self) -> Path:
        return self.root / "config.json"

    @property
    def key_path(self) -> Path:
        return self.secrets_dir / f"{self.provider}.key"

    def load_key(self) -> str | None:
        if self.key_path.is_file():
            s = self.key_path.read_text(encoding="utf-8").strip()
            if s:
                return s
        env = _KEY_ENV.get(self.provider, "")
        v = os.environ.get(env) if env else None
        return v.strip() if v else None

    def build_backend(self):
        # claude-cli authenticates with the Claude subscription via the `claude`
        # CLI itself (keychain OAuth, or a durable setup-token for headless runs),
        # so it needs no API key at all.
        if self.provider == "claude-cli":
            return ClaudeCLIBackend(root=self.root, model=self.model or "")
        key = self.load_key()
        if not key:
            raise RuntimeError(f"no key for '{self.provider}' (looked in {self.key_path} and env)")
        if self.provider == "anthropic":
            return AnthropicBackend(key, default_model=self.model or ANTHROPIC_DEFAULT_MODEL)
        if self.provider == "openai":
            if not self.model:
                raise RuntimeError("openai requires a model id in config (no hardcoded frontier-id guess)")
            return OpenAIBackend(key, default_model=self.model)
        if self.provider == "openai-responses":
            if not self.model:
                raise RuntimeError("openai-responses requires a model id in config (no hardcoded frontier-id guess)")
            return ResponsesBackend(key, default_model=self.model)
        if self.provider == "gemini":
            return GeminiBackend(key, default_model=self.model or GEMINI_DEFAULT_MODEL)
        raise RuntimeError(f"unknown provider {self.provider!r}")


def load(root: Path | None = None, *, creating: bool = False) -> GenesisConfig:
    """Read the config for the active home.

    `creating=True` is the caller saying "this command is allowed to stand up a new
    home" (init, install, onboard). Everything else gets the guard, so no ordinary
    command can fork an agent into a fresh empty vault. See resolve_root().
    """
    # Coerce: the annotation says Path, and a caller passing a plain string
    # otherwise gets a TypeError several lines later at a path join, which
    # names neither the argument nor the caller.
    root = Path(root).expanduser() if root else resolve_root(creating=creating)
    data: dict = {}
    cfgp = root / "config.json"
    if cfgp.is_file():
        # utf-8-sig tolerates a leading BOM: Windows editors and PowerShell's
        # `Set-Content -Encoding utf8` prepend one, and plain utf-8 chokes on it.
        data = json.loads(cfgp.read_text(encoding="utf-8-sig"))
    recipients = data.get("allowed_email_recipients") or None  # None → default
    trains = data.get("engine_trains")  # None unless explicitly set
    machinery = data.get("machinery") if isinstance(data.get("machinery"), dict) else None
    return GenesisConfig(
        root=root,
        provider=data.get("provider", "anthropic"),
        model=data.get("model"),
        allowed_email_recipients=recipients,
        trains=trains if isinstance(trains, bool) else None,
        machinery=machinery,
        sponsor_sender=data.get("sponsor_sender"),
        name=(data.get("name") or None),
        project_repo=(data.get("project_repo") or None),
        drip=bool(data.get("drip", False)),
        harnesses=[h for h in (data.get("harnesses") or []) if isinstance(h, str)],
    )


def update_fields(cfg: "GenesisConfig", **fields) -> None:
    """Write a few non-secret fields into config.json without disturbing the rest.
    `save()` below only knows provider/model and would erase everything else; this
    is the narrow writer the name/project/drip/harness paths use."""
    data: dict = {}
    if cfg.config_path.is_file():
        try:
            data = json.loads(cfg.config_path.read_text(encoding="utf-8-sig"))
        except Exception:
            data = {}
    for k, v in fields.items():
        if v is None:
            data.pop(k, None)
        else:
            data[k] = v
    cfg.root.mkdir(parents=True, exist_ok=True)
    tmp = cfg.config_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(cfg.config_path)


def save(cfg: GenesisConfig) -> None:
    cfg.root.mkdir(parents=True, exist_ok=True)
    cfg.config_path.write_text(
        json.dumps({"provider": cfg.provider, "model": cfg.model}, indent=2), encoding="utf-8"
    )
