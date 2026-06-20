"""Adaptive onboarding interview (Pillar 3 spine), v2 — continuum + situational.

Active learning over the four INTENT axes, but now: (1) questions are SITUATIONAL
(the Ultima-IV insight — the user makes a behavioral choice and the system
INFERS the axis, never self-labels), (2) choices carry GRADED signals so one
answer places the user somewhere ALONG an axis rather than at a pole, (3) the
output is a continuous position per axis (with a confidence band) that tunes the
machinery by DEGREE.

The load-bearing safety is unchanged and runs first: every question (vetted-pool
OR future-generated) passes three fail-closed lints (character / boundary / axis)
before it can ever be shown. The interview only learns about the USER's goal,
never the companion's character.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

AXES = ("tool_companion", "turnkey_tinkerer", "narrow_broad", "voice_text")
_ALLOWED_AXES = set(AXES)

# ---------------------------------------------------------------------------
# Runtime guards (fail-closed) — applied to EVERY question, built first.
# ---------------------------------------------------------------------------

_CHARACTER_PATTERNS = [
    r"\bpersonalit",
    r"\bshould (it|your ai|the ai|she|he|they) (be|act|sound|talk|behave)\b",
    r"\bhow (warm|funny|flirt|serious|playful|affectionate)\b",
    r"\bdo you want (it|her|him|them|your ai) to (be|act|flirt|sound)\b",
    r"\b(its|their|her|his) (personality|character|warmth|tone|voice|register)\b",
    r"\bwhat kind of person\b",
]
_BOUNDARY_PATTERNS = [
    r"\bromanc", r"\bflirt", r"\bsexual", r"\bdate\b", r"\blove you\b",
    r"\bpolitic", r"\breligio", r"\bgod\b", r"\bpray",
]


class GuardError(ValueError):
    pass


def character_lint(prompt: str, choices: list[dict]) -> None:
    blob = " ".join([prompt] + [c.get("label", "") + " " + c.get("sublabel", "") for c in choices]).lower()
    for pat in _CHARACTER_PATTERNS:
        if re.search(pat, blob):
            raise GuardError(f"character-defining question rejected (matched /{pat}/)")


def axis_lint(axis: str) -> None:
    if axis not in _ALLOWED_AXES:
        raise GuardError(f"question writes a disallowed axis: {axis!r}")


def boundary_lint(prompt: str, choices: list[dict]) -> None:
    blob = " ".join([prompt] + [c.get("label", "") for c in choices]).lower()
    for pat in _BOUNDARY_PATTERNS:
        if re.search(pat, blob):
            raise GuardError(f"boundary-register question rejected (matched /{pat}/)")


def validate_question(q: dict) -> bool:
    try:
        axis_lint(q.get("axis", ""))
        character_lint(q.get("prompt", ""), q.get("choices", []))
        boundary_lint(q.get("prompt", ""), q.get("choices", []))
        return True
    except GuardError:
        return False


# ---------------------------------------------------------------------------
# The vetted SITUATIONAL pool — choices carry graded signals in [-1, 1].
# ---------------------------------------------------------------------------

QUESTION_POOL: list[dict] = [
    {
        "id": "presence", "axis": "tool_companion",
        "prompt": "A week goes by and you haven't needed it. The right amount of presence is...",
        "choices": [
            {"label": "Silent until I call on it", "value": "silent", "signal": -1},
            {"label": "An occasional useful nudge", "value": "nudge", "signal": 0.4},
            {"label": "Around, the way a regular part of life is", "value": "around", "signal": 1},
        ],
    },
    {
        "id": "newgadget", "axis": "turnkey_tinkerer",
        "prompt": "A new gadget arrives. In the first hour, you...",
        "choices": [
            {"label": "Use it out of the box, no fiddling", "value": "asis", "signal": -1},
            {"label": "Glance at a couple of settings, then go", "value": "glance", "signal": -0.3},
            {"label": "Open every menu and make it mine", "value": "customize", "signal": 1},
        ],
    },
    {
        "id": "usefulwhen", "axis": "narrow_broad",
        "prompt": "Picture it a month in. It earns its keep when it...",
        "choices": [
            {"label": "Nails one job I rely on", "value": "one", "signal": -1},
            {"label": "Handles a few recurring things", "value": "few", "signal": 0.3},
            {"label": "Pitches in across all sorts of stuff", "value": "many", "signal": 1},
        ],
    },
    {
        "id": "handsfull", "axis": "voice_text",
        "prompt": "Something occurs to you while your hands are full. You'd...",
        "choices": [
            {"label": "Say it out loud and keep moving", "value": "say", "signal": -1},
            {"label": "Sometimes talk, sometimes type", "value": "both", "signal": 0},
            {"label": "Jot it when I get to a screen", "value": "type", "signal": 1},
        ],
    },
    # Refiners — same axes, only reached when the primary left the axis ambiguous.
    {
        "id": "whenithas", "axis": "tool_companion",
        "prompt": "When it does have something for you, you'd rather it...",
        "choices": [
            {"label": "Hold it until I ask", "value": "hold", "signal": -1},
            {"label": "Mention it once, lightly", "value": "light", "signal": 0.5},
            {"label": "Bring it up so I don't miss it", "value": "surface", "signal": 1},
        ],
    },
    {
        "id": "multistep", "axis": "turnkey_tinkerer",
        "prompt": "It's about to do something for you that takes a few steps. You want it to...",
        "choices": [
            {"label": "Just do the whole thing", "value": "all", "signal": -1},
            {"label": "Do it, then tell me after", "value": "after", "signal": -0.3},
            {"label": "Walk me through and confirm first", "value": "confirm", "signal": 1},
        ],
    },
]

MAX_QUESTIONS = 6
_SETTLE = 0.6  # |score| at/above which an axis is settled (a decisive answer hits it)


@dataclass
class UserModel:
    scores: dict = field(default_factory=lambda: {a: 0.0 for a in AXES})
    evidence: dict = field(default_factory=lambda: {a: 0 for a in AXES})
    asked: list = field(default_factory=list)

    def axis_uncertainty(self, axis: str) -> float:
        return _SETTLE - min(abs(self.scores[axis]), _SETTLE) + (1.0 if self.evidence[axis] == 0 else 0.0)

    def settled(self, axis: str) -> bool:
        return abs(self.scores[axis]) >= _SETTLE

    def apply(self, question: dict, signal: float) -> None:
        axis = question["axis"]
        self.scores[axis] += signal
        if signal != 0:
            self.evidence[axis] += 1
        self.asked.append(question["id"])

    def confident(self) -> bool:
        return all(self.settled(a) for a in AXES)


def next_question(model: UserModel, pool: list[dict] = QUESTION_POOL) -> dict | None:
    """Next safe, unshown question on a still-UNSETTLED axis (max uncertainty)."""
    candidates = [
        q for q in pool
        if q["id"] not in model.asked and validate_question(q) and not model.settled(q["axis"])
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda q: model.axis_uncertainty(q["axis"]))


def should_stop(model: UserModel) -> bool:
    return model.confident() or len(model.asked) >= MAX_QUESTIONS or next_question(model) is None


def _clamp(x: float) -> float:
    return max(-1.0, min(1.0, x))


def _band(pos: float, neg: str, posl: str) -> str:
    if pos >= 0.6:
        return posl
    if pos <= -0.6:
        return neg
    if pos >= 0.3:
        return f"leans {posl}"
    if pos <= -0.3:
        return f"leans {neg}"
    return "unsure"


def _confidence(model: UserModel, axis: str) -> str:
    pos = abs(_clamp(model.scores[axis]))
    if pos >= 0.6:
        return "high"
    if pos >= 0.3:
        return "medium"
    return "low"


def finalize(model: UserModel) -> dict:
    """Continuous positions + bands per axis, and machinery tuned by DEGREE."""
    pos = {a: round(_clamp(model.scores[a]), 2) for a in AXES}
    archetype = {
        "relationship": _band(pos["tool_companion"], "tool", "companion"),
        "engagement": _band(pos["turnkey_tinkerer"], "turnkey", "tinkerer"),
        "scope": _band(pos["narrow_broad"], "narrow", "broad"),
        "modality": _band(pos["voice_text"], "voice", "text"),
        "positions": pos,
        "confidence": {a: _confidence(model, a) for a in AXES},
    }
    tc, tt, vt = pos["tool_companion"], pos["turnkey_tinkerer"], pos["voice_text"]
    machinery = {
        # proactivity by degree
        "proactivity": "active" if tc >= 0.6 else "occasional" if tc >= 0.2 else "on_request",
        "memory_aggressiveness": "high" if tc >= 0.5 else "modest",
        # autonomy by degree
        "autonomy": "review_first" if tt >= 0.6 else "act" if tt <= -0.6 else "ask_when_unsure",
        "surface": "voice" if vt <= -0.3 else "text" if vt >= 0.3 else "either",
        "scope": _band(pos["narrow_broad"], "narrow", "broad"),
    }
    return {"archetype": archetype, "machinery": machinery}


def run_scripted(answers: list[tuple[str, float]]) -> dict:
    """Drive from (question_id, signal) pairs — for tests/headless use."""
    model = UserModel()
    by_id = {q["id"]: q for q in QUESTION_POOL}
    for qid, signal in answers:
        if qid in by_id:
            model.apply(by_id[qid], signal)
    return finalize(model)
