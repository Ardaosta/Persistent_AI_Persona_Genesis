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
# reach when stuck. `mode` picks the runtime: "agent" (Mode A, Genesis runs the
# loop on the chosen engine) or "claude-code" (Mode B, Claude Code is the brain,
# Genesis the memory). Conditions, never content.
# Added 2026-09-10: `name` (the person's chosen name for the AI, or empty to let
# it name itself), `harnesses` (which Mode-B doors to wire: claude-code, codex,
# or both; `mode` stays the primary), `project_repo` (a repository the AI is
# joining, so it can import that project's seed pack), and `drip` (opt-in to
# the getting-to-know-you question drip). Still conditions, never content.
# Added 2026-09-21: `capabilities`, the domains the person asked for help with
# (website, social, calendar, email, finances). Each slug is a pointer at a
# content-free recipe copied into the vault at init; the manual lists them. A
# slug not in CAPABILITIES is dropped, so a seed can never point at a file it
# did not ship. Conditions, never content.
# Also 2026-09-21: `services`, the named online services the person ALREADY uses
# and wants help managing (wix, ...). A capability is a kind of work; a service
# is a specific account. A sponsor who knows the person's setup may name them at
# seed time; otherwise the AI discovers them over time (the services loop in the
# manual) and adds them with `genesis services --add`. Never presupposed: the
# generic flow ships no services. Conditions, never content.
# Also 2026-09-21: `helper`, remote help. A sponsor preparing a link may include
# their PUBLIC ssh keys; the person decides ON SCREEN whether to allow it, and
# only a consented helper rides into the download. The installer then turns on
# the machine's login service and installs those keys, so nobody has to carry a
# file by hand (getting one 2.5KB script onto a laptop took four attempts the
# day this was added). Public keys only, validated by shape; `consented` must be
# exactly true for anything to happen; the person can remove it later.
_ALLOWED = {"v", "archetype", "machinery", "look", "provider", "sponsor", "mode",
            "name", "harnesses", "project_repo", "drip", "capabilities", "services",
            "helper"}
HARNESSES = ("claude-code", "codex")
CAPABILITIES = ("website", "social", "calendar", "email", "finances")
SERVICES = ("wix",)

import re as _re

HELPER_KEY_RE = _re.compile(r"^(ssh-ed25519|ecdsa-sha2-nistp256|ssh-rsa) [A-Za-z0-9+/=]+( [^\s]{1,64})?$")
HELPER_KEY_MAX = 600
HELPER_KEYS_MAX = 4
HELPER_NAME_MAX = 40


def clean_helper(value) -> "dict | None":
    """Keep a helper only when shape-valid with at least one valid PUBLIC key.
    Mirrors web/lib/seed.ts cleanHelper exactly: invalid keys dropped, at most
    four, name display-only and sanitized, consented coerced to a strict bool."""
    if not isinstance(value, dict) or not isinstance(value.get("keys"), list):
        return None
    keys = []
    for k in value["keys"]:
        if not isinstance(k, str):
            continue
        t = k.strip()
        if len(t) > HELPER_KEY_MAX or not HELPER_KEY_RE.match(t) or t in keys:
            continue
        keys.append(t)
        if len(keys) >= HELPER_KEYS_MAX:
            break
    if not keys:
        return None
    name = value.get("name") if isinstance(value.get("name"), str) else ""
    name = _re.sub(r"[^\w' .-]", "", name, flags=_re.UNICODE).strip()[:HELPER_NAME_MAX]
    return {"name": name, "keys": keys, "consented": value.get("consented") is True}


def _clean_slugs(value, known) -> list:
    """Keep known slugs, in the order given, without duplicates."""
    if not isinstance(value, (list, tuple)):
        return []
    out = []
    for x in value:
        if isinstance(x, str) and x in known and x not in out:
            out.append(x)
    return out


def clean_capabilities(value) -> list:
    return _clean_slugs(value, CAPABILITIES)


def clean_services(value) -> list:
    return _clean_slugs(value, SERVICES)


def make_seed(
    *,
    archetype: dict | None = None,
    machinery: dict | None = None,
    look: str | None = None,
    provider: str | None = None,
    sponsor: str | None = None,
    mode: str | None = None,
    name: str | None = None,
    harnesses: list | None = None,
    project_repo: str | None = None,
    drip: bool = False,
    capabilities: list | None = None,
    services: list | None = None,
    helper: dict | None = None,
) -> dict:
    return {
        "v": SEED_VERSION,
        "archetype": archetype or {},
        "machinery": machinery or {},
        "look": look or None,
        "provider": provider or None,
        "sponsor": sponsor or None,
        "mode": mode or None,
        "name": (name or "").strip()[:60] or None,
        "harnesses": [h for h in (harnesses or []) if h in HARNESSES],
        "project_repo": (project_repo or "").strip()[:300] or None,
        "drip": bool(drip),
        "capabilities": clean_capabilities(capabilities),
        "services": clean_services(services),
        "helper": clean_helper(helper),
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
    # Coerce the 2026-09-10 keys the same way: a malformed seed degrades, never crashes.
    clean["harnesses"] = [h for h in (clean.get("harnesses") or []) if h in HARNESSES] \
        if isinstance(clean.get("harnesses"), list) else []
    clean["name"] = str(clean["name"]).strip()[:60] if clean.get("name") else None
    clean["project_repo"] = str(clean["project_repo"]).strip()[:300] if clean.get("project_repo") else None
    clean["drip"] = bool(clean.get("drip", False))
    clean["capabilities"] = clean_capabilities(clean.get("capabilities"))
    clean["services"] = clean_services(clean.get("services"))
    clean["helper"] = clean_helper(clean.get("helper"))
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
