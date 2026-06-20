"""The interface-directive protocol: the guide's SECOND CHANNEL.

Alongside the words it speaks, the onboarding guide emits *interface directives*
— it calls these the same way it calls remember/shell_run. Each directive is a
small, strictly-validated instruction the adaptive front end animates into being:
a palette the moment it learns your aesthetic, a typographic register for your
voice, a capability control unlocked RPG-style when the conversation reaches the
moment you'd want it.

Design decisions:
- "Vocabulary now, generative seam later": the model chooses among a BOUNDED set
  of pre-designed mutations. The artistry (the actual transitions) lives in the
  front end; the model supplies taste in *which* directive and *when*. A
  RAW_BLOCK directive is reserved as the forward seam for generative UI later —
  it is defined but NOT yet exposed as a tool.
- "Permanent surface": every directive folds into an InterfaceProfile that
  persists, so what the interface becomes is the daily driver, not onboarding
  theater.

This module is renderer-agnostic and zero-dep: it defines the vocabulary, a
strict validator (a malformed directive must never reach the screen), the
InterfaceProfile accumulator, and the ToolSpec objects. The Next.js canvas is a
separate consumer of the validated directive stream.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path

from genesis_backend import ToolSpec

# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------

# Capabilities the guide may unlock. Kept closed: a capability the host can't
# actually render is worse than none. Grows as the front end learns to render more.
CAPABILITIES = ("voice", "screenshare", "photos", "email", "files")

# Typographic registers — named, pre-designed pairings the front end owns.
TYPE_REGISTERS = ("plain", "editorial", "cinematic", "technical", "gentle")

_HEX = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")

# A palette needs at least a base + accent; text is optional (front end derives a
# readable default from base if omitted).
_PALETTE_KEYS = ("base", "accent", "text")


class DirectiveError(ValueError):
    """A directive failed validation and must not reach the screen."""


def _need_hex(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not _HEX.match(value):
        raise DirectiveError(f"{field_name} must be a hex color like #10243b, got {value!r}")


def validate(directive: dict) -> dict:
    """Validate one directive. Returns the normalized directive or raises DirectiveError."""
    if not isinstance(directive, dict):
        raise DirectiveError("directive must be an object")
    kind = directive.get("kind")
    if kind == "setPalette":
        pal = directive.get("palette")
        if not isinstance(pal, dict):
            raise DirectiveError("setPalette needs a palette object")
        if "base" not in pal or "accent" not in pal:
            raise DirectiveError("palette needs at least base and accent")
        clean = {}
        for k in _PALETTE_KEYS:
            if k in pal and pal[k] is not None:
                _need_hex(pal[k], f"palette.{k}")
                clean[k] = pal[k]
        return {"kind": "setPalette", "palette": clean}
    if kind == "setType":
        reg = directive.get("register")
        if reg not in TYPE_REGISTERS:
            raise DirectiveError(f"register must be one of {TYPE_REGISTERS}, got {reg!r}")
        out = {"kind": "setType", "register": reg}
        if directive.get("scale") is not None:
            scale = directive["scale"]
            if scale not in ("normal", "large", "xl"):
                raise DirectiveError("scale must be normal|large|xl")
            out["scale"] = scale
        return out
    if kind == "unlockCapability":
        cap = directive.get("capability")
        if cap not in CAPABILITIES:
            raise DirectiveError(f"capability must be one of {CAPABILITIES}, got {cap!r}")
        return {"kind": "unlockCapability", "capability": cap}
    if kind == "emphasize":
        text = directive.get("text", "")
        if not isinstance(text, str) or not text.strip():
            raise DirectiveError("emphasize needs non-empty text")
        return {"kind": "emphasize", "text": text.strip()[:280]}
    raise DirectiveError(f"unknown directive kind {kind!r}")


# ---------------------------------------------------------------------------
# InterfaceProfile — the persisted accumulation (the "permanent surface")
# ---------------------------------------------------------------------------

@dataclass
class InterfaceProfile:
    palette: dict = field(default_factory=dict)
    register: str | None = None
    scale: str = "normal"
    unlocked: list = field(default_factory=list)

    def apply(self, directive: dict) -> dict:
        """Fold a (pre-validated) directive into the profile. Returns the directive."""
        kind = directive["kind"]
        if kind == "setPalette":
            self.palette = dict(directive["palette"])
        elif kind == "setType":
            self.register = directive["register"]
            if "scale" in directive:
                self.scale = directive["scale"]
        elif kind == "unlockCapability":
            cap = directive["capability"]
            if cap not in self.unlocked:
                self.unlocked.append(cap)
        # emphasize is transient — it animates but doesn't persist into the profile
        return directive

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "InterfaceProfile":
        return cls(
            palette=dict(data.get("palette") or {}),
            register=data.get("register"),
            scale=data.get("scale", "normal"),
            unlocked=list(data.get("unlocked") or []),
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "InterfaceProfile":
        if not path.exists():
            return cls()
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))


# ---------------------------------------------------------------------------
# Tool implementations (return strings for the model; never raise)
# ---------------------------------------------------------------------------

def _ok(directive: dict) -> str:
    # The model only needs confirmation; the validated directive goes to the
    # renderer out-of-band (the Session collects emitted directives).
    return f"applied: {directive['kind']}"


def tool_set_palette(profile: InterfaceProfile, base: str, accent: str, text: str | None = None) -> tuple[str, dict | None]:
    pal = {"base": base, "accent": accent}
    if text:
        pal["text"] = text
    try:
        d = validate({"kind": "setPalette", "palette": pal})
    except DirectiveError as e:
        return f"rejected: {e}", None
    profile.apply(d)
    return _ok(d), d


def tool_set_type(profile: InterfaceProfile, register: str, scale: str | None = None) -> tuple[str, dict | None]:
    raw = {"kind": "setType", "register": register}
    if scale:
        raw["scale"] = scale
    try:
        d = validate(raw)
    except DirectiveError as e:
        return f"rejected: {e}", None
    profile.apply(d)
    return _ok(d), d


def tool_unlock_capability(profile: InterfaceProfile, capability: str) -> tuple[str, dict | None]:
    try:
        d = validate({"kind": "unlockCapability", "capability": capability})
    except DirectiveError as e:
        return f"rejected: {e}", None
    profile.apply(d)
    return _ok(d), d


def tool_emphasize(profile: InterfaceProfile, text: str) -> tuple[str, dict | None]:
    try:
        d = validate({"kind": "emphasize", "text": text})
    except DirectiveError as e:
        return f"rejected: {e}", None
    profile.apply(d)
    return _ok(d), d


# ---------------------------------------------------------------------------
# ToolSpec objects
# ---------------------------------------------------------------------------

SET_PALETTE_TOOL = ToolSpec(
    name="set_palette",
    description=(
        "Apply a color palette to the interface the MOMENT you learn this person's "
        "aesthetic — their favorite colors, the mood they want, a world they love. "
        "Colors are hex (e.g. #10243b). base = the canvas, accent = highlights/controls, "
        "text = optional (omit and a readable default is derived). Call this as soon as "
        "you have a real signal; don't wait."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "base": {"type": "string", "description": "hex color for the canvas background"},
            "accent": {"type": "string", "description": "hex color for highlights and controls"},
            "text": {"type": "string", "description": "optional hex color for text"},
        },
        "required": ["base", "accent"],
    },
)

SET_TYPE_TOOL = ToolSpec(
    name="set_type",
    description=(
        "Style the interface's typographic LOOK (the screen's presentation, not how "
        "you speak; your own voice is yours to grow, never theirs to set). One of: "
        "plain, editorial, cinematic, technical, gentle. Optional scale: normal, large "
        "(easier to read), xl. Use 'gentle' + 'large' for someone who'd like it easy to "
        "read; 'cinematic' for someone who wants a little magic; 'technical' for a maker."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "register": {"type": "string", "enum": list(TYPE_REGISTERS)},
            "scale": {"type": "string", "enum": ["normal", "large", "xl"]},
        },
        "required": ["register"],
    },
)

UNLOCK_CAPABILITY_TOOL = ToolSpec(
    name="unlock_capability",
    description=(
        "Reveal a new capability control on screen, RPG-style — the moment the "
        "conversation shows this person would want it, NOT before. One of: voice, "
        "screenshare, photos, email, files. Example: they say they'd rather talk than "
        "type -> unlock_capability('voice'). Introduce one at a time, when it's earned."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "capability": {"type": "string", "enum": list(CAPABILITIES)},
        },
        "required": ["capability"],
    },
)

EMPHASIZE_TOOL = ToolSpec(
    name="emphasize",
    description=(
        "Make a short phrase land with visual weight — a welcome, a name, a moment that "
        "matters. Transient: it animates but doesn't change the saved interface. Use "
        "sparingly, for real beats."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "the short phrase to emphasize"},
        },
        "required": ["text"],
    },
)

INTERFACE_TOOLS = [SET_PALETTE_TOOL, SET_TYPE_TOOL, UNLOCK_CAPABILITY_TOOL, EMPHASIZE_TOOL]
