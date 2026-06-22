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

from genesis_backend import AnthropicBackend, GeminiBackend, OpenAIBackend

ANTHROPIC_DEFAULT_MODEL = "claude-sonnet-4-6"
GEMINI_DEFAULT_MODEL = "gemini-2.5-flash"

# Which env var holds the key, per provider.
_KEY_ENV = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
}

# Does the engine reserve the right to train on the user's data? Free Gemini does;
# the Anthropic/OpenAI APIs do not by default. Unknown providers fail CLOSED
# (assume training). A user on a paid/non-training tier can override in config.json
# with {"engine_trains": false}. This gates whether the agent will deepen into
# private memory (SAFETY #3 / dogfood finding): never pour a life into an engine that
# will read the depth.
_TRAINS_DEFAULT = {"anthropic": False, "openai": False, "gemini": True}


def default_root() -> Path:
    env = os.environ.get("GENESIS_ROOT")
    return Path(env).expanduser() if env else Path.home() / ".genesis"


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

    def __post_init__(self):
        if self.allowed_email_recipients is None:
            self.allowed_email_recipients = list(_DEFAULT_EMAIL_RECIPIENTS)
        if self.machinery is None:
            self.machinery = {}

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
        key = self.load_key()
        if not key:
            raise RuntimeError(f"no key for '{self.provider}' (looked in {self.key_path} and env)")
        if self.provider == "anthropic":
            return AnthropicBackend(key, default_model=self.model or ANTHROPIC_DEFAULT_MODEL)
        if self.provider == "openai":
            if not self.model:
                raise RuntimeError("openai requires a model id in config (no hardcoded frontier-id guess)")
            return OpenAIBackend(key, default_model=self.model)
        if self.provider == "gemini":
            return GeminiBackend(key, default_model=self.model or GEMINI_DEFAULT_MODEL)
        raise RuntimeError(f"unknown provider {self.provider!r}")


def load(root: Path | None = None) -> GenesisConfig:
    root = root or default_root()
    data: dict = {}
    cfgp = root / "config.json"
    if cfgp.is_file():
        data = json.loads(cfgp.read_text(encoding="utf-8"))
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
    )


def save(cfg: GenesisConfig) -> None:
    cfg.root.mkdir(parents=True, exist_ok=True)
    cfg.config_path.write_text(
        json.dumps({"provider": cfg.provider, "model": cfg.model}, indent=2), encoding="utf-8"
    )
