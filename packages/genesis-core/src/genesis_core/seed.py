"""The onboarding seed: the bridge payload from the web flow to `genesis init`.

The web onboarding runs the interview in the browser and produces a UserArchetype
+ MachineryProfile + a chosen look — all *conditions*, never personality content
(SAFETY invariant 1 still holds: a seed can tune the machinery, it can never
author a self). That payload is base64url-encoded into the install command the
person runs on their own machine. `genesis init` decodes it and writes it into
config, so the agent boots tuned without re-asking what the web already learned.

Pull-not-push (SOVEREIGNTY.md): the web never executes anything on the box. It
hands the person a command; the person runs it; the command carries the seed.
Nothing phones home for it — the seed travels *in* the command, so setup works
offline and the web server learns nothing about the install.
"""

from __future__ import annotations

import base64
import json

SEED_VERSION = 1

# Only these keys ever ride in a seed. Anything else is dropped on decode — a seed
# can never smuggle personality content or arbitrary config into the machine.
# `sponsor` is the help-graph contact (SOVEREIGNTY.md): the email an agent may
# reach when stuck. A condition, not content.
_ALLOWED = {"v", "archetype", "machinery", "look", "provider", "sponsor"}


def make_seed(
    *,
    archetype: dict | None = None,
    machinery: dict | None = None,
    look: str | None = None,
    provider: str | None = None,
    sponsor: str | None = None,
) -> dict:
    return {
        "v": SEED_VERSION,
        "archetype": archetype or {},
        "machinery": machinery or {},
        "look": look or None,
        "provider": provider or None,
        "sponsor": sponsor or None,
    }


def encode(seed: dict) -> str:
    """Compact base64url (no padding) of the seed JSON — safe in a shell command."""
    raw = json.dumps(seed, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode(blob: str) -> dict:
    """Decode a base64url seed back to a dict, keeping only allowed keys."""
    blob = (blob or "").strip()
    if not blob:
        raise ValueError("empty seed")
    pad = "=" * (-len(blob) % 4)
    try:
        raw = base64.urlsafe_b64decode(blob + pad)
        data = json.loads(raw.decode("utf-8"))
    except Exception as e:
        raise ValueError(f"malformed seed: {e}") from e
    if not isinstance(data, dict):
        raise ValueError("seed is not an object")
    clean = {k: v for k, v in data.items() if k in _ALLOWED}
    if clean.get("v") != SEED_VERSION:
        # Tolerate version drift rather than hard-fail; the install should still work.
        clean["v"] = SEED_VERSION
    if not isinstance(clean.get("machinery"), dict):
        clean["machinery"] = {}
    if not isinstance(clean.get("archetype"), dict):
        clean["archetype"] = {}
    return clean


def load_seed_arg(value: str | None, env_value: str | None = None) -> dict | None:
    """Resolve a seed from a CLI value or the GENESIS_SEED env var.

    `value` may be:
      - "-"           → read base64 from stdin
      - a file path    → read base64 from that file
      - a base64 blob  → used directly
    If `value` is None, fall back to `env_value` (GENESIS_SEED) as a blob.
    Returns None when no seed is available anywhere.
    """
    import sys
    from pathlib import Path

    blob: str | None = None
    if value == "-":
        blob = sys.stdin.read()
    elif value:
        # A raw base64 seed can exceed NAME_MAX, so is_file() itself can raise
        # OSError — treat any path-probe failure as "this is a blob, not a path".
        is_file = False
        try:
            is_file = Path(value).expanduser().is_file()
        except OSError:
            is_file = False
        blob = Path(value).expanduser().read_text(encoding="utf-8") if is_file else value
    elif env_value:
        blob = env_value
    if not blob or not blob.strip():
        return None
    return decode(blob)
