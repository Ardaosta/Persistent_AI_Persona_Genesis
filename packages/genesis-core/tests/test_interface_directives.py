"""Tests for the interface-directive protocol (zero-dep, stdlib unittest)."""

import json
import tempfile
import unittest
from pathlib import Path

from genesis_core.interface_directives import (
    CAPABILITIES,
    INTERFACE_TOOLS,
    TYPE_REGISTERS,
    DirectiveError,
    InterfaceProfile,
    tool_emphasize,
    tool_set_palette,
    tool_set_type,
    tool_unlock_capability,
    validate,
)


class TestValidate(unittest.TestCase):
    def test_valid_palette(self):
        d = validate({"kind": "setPalette", "palette": {"base": "#10243b", "accent": "#2dd4bf"}})
        self.assertEqual(d["kind"], "setPalette")
        self.assertEqual(d["palette"]["base"], "#10243b")

    def test_palette_three_digit_hex_ok(self):
        d = validate({"kind": "setPalette", "palette": {"base": "#abc", "accent": "#def"}})
        self.assertEqual(d["palette"]["base"], "#abc")

    def test_palette_bad_hex_rejected(self):
        with self.assertRaises(DirectiveError):
            validate({"kind": "setPalette", "palette": {"base": "navy", "accent": "#2dd4bf"}})

    def test_palette_missing_accent_rejected(self):
        with self.assertRaises(DirectiveError):
            validate({"kind": "setPalette", "palette": {"base": "#10243b"}})

    def test_palette_drops_unknown_keys(self):
        d = validate({"kind": "setPalette", "palette": {"base": "#10243b", "accent": "#2dd4bf", "evil": "x"}})
        self.assertNotIn("evil", d["palette"])

    def test_valid_type(self):
        d = validate({"kind": "setType", "register": "cinematic"})
        self.assertEqual(d["register"], "cinematic")

    def test_type_bad_register_rejected(self):
        with self.assertRaises(DirectiveError):
            validate({"kind": "setType", "register": "comic-sans-party"})

    def test_type_scale_validated(self):
        d = validate({"kind": "setType", "register": "gentle", "scale": "large"})
        self.assertEqual(d["scale"], "large")
        with self.assertRaises(DirectiveError):
            validate({"kind": "setType", "register": "gentle", "scale": "ENORMOUS"})

    def test_valid_unlock(self):
        d = validate({"kind": "unlockCapability", "capability": "voice"})
        self.assertEqual(d["capability"], "voice")

    def test_unlock_unknown_capability_rejected(self):
        with self.assertRaises(DirectiveError):
            validate({"kind": "unlockCapability", "capability": "launch_missiles"})

    def test_emphasize_ok_and_truncates(self):
        d = validate({"kind": "emphasize", "text": "x" * 500})
        self.assertEqual(d["kind"], "emphasize")
        self.assertLessEqual(len(d["text"]), 280)

    def test_emphasize_empty_rejected(self):
        with self.assertRaises(DirectiveError):
            validate({"kind": "emphasize", "text": "   "})

    def test_unknown_kind_rejected(self):
        with self.assertRaises(DirectiveError):
            validate({"kind": "rm_rf_screen"})

    def test_non_dict_rejected(self):
        with self.assertRaises(DirectiveError):
            validate("setPalette")


class TestInterfaceProfile(unittest.TestCase):
    def test_palette_folds_in(self):
        p = InterfaceProfile()
        p.apply(validate({"kind": "setPalette", "palette": {"base": "#10243b", "accent": "#2dd4bf"}}))
        self.assertEqual(p.palette["base"], "#10243b")

    def test_type_folds_in(self):
        p = InterfaceProfile()
        p.apply(validate({"kind": "setType", "register": "cinematic", "scale": "xl"}))
        self.assertEqual(p.register, "cinematic")
        self.assertEqual(p.scale, "xl")

    def test_unlock_accumulates_without_dupes(self):
        p = InterfaceProfile()
        p.apply(validate({"kind": "unlockCapability", "capability": "voice"}))
        p.apply(validate({"kind": "unlockCapability", "capability": "voice"}))
        p.apply(validate({"kind": "unlockCapability", "capability": "email"}))
        self.assertEqual(p.unlocked, ["voice", "email"])

    def test_emphasize_does_not_persist(self):
        p = InterfaceProfile()
        before = p.to_dict()
        p.apply(validate({"kind": "emphasize", "text": "Welcome back"}))
        self.assertEqual(p.to_dict(), before)

    def test_roundtrip_save_load(self):
        p = InterfaceProfile()
        p.apply(validate({"kind": "setPalette", "palette": {"base": "#f4efe6", "accent": "#b07a3c"}}))
        p.apply(validate({"kind": "setType", "register": "gentle", "scale": "large"}))
        p.apply(validate({"kind": "unlockCapability", "capability": "photos"}))
        td = Path(tempfile.mkdtemp())
        path = td / "vault" / "interface_profile.json"
        p.save(path)
        loaded = InterfaceProfile.load(path)
        self.assertEqual(loaded.palette["accent"], "#b07a3c")
        self.assertEqual(loaded.register, "gentle")
        self.assertEqual(loaded.scale, "large")
        self.assertEqual(loaded.unlocked, ["photos"])

    def test_load_missing_returns_empty(self):
        loaded = InterfaceProfile.load(Path("/tmp/does-not-exist-genesis/profile.json"))
        self.assertEqual(loaded.palette, {})
        self.assertIsNone(loaded.register)


class TestTools(unittest.TestCase):
    def test_set_palette_returns_directive(self):
        p = InterfaceProfile()
        msg, d = tool_set_palette(p, "#10243b", "#2dd4bf")
        self.assertIn("applied", msg)
        self.assertEqual(d["kind"], "setPalette")
        self.assertEqual(p.palette["base"], "#10243b")

    def test_set_palette_bad_hex_rejected_gracefully(self):
        p = InterfaceProfile()
        msg, d = tool_set_palette(p, "blue", "#2dd4bf")
        self.assertIn("rejected", msg)
        self.assertIsNone(d)
        self.assertEqual(p.palette, {})  # unchanged

    def test_set_type_tool(self):
        p = InterfaceProfile()
        msg, d = tool_set_type(p, "technical")
        self.assertIn("applied", msg)
        self.assertEqual(p.register, "technical")

    def test_unlock_tool(self):
        p = InterfaceProfile()
        msg, d = tool_unlock_capability(p, "screenshare")
        self.assertIn("applied", msg)
        self.assertIn("screenshare", p.unlocked)

    def test_unlock_bad_capability_rejected(self):
        p = InterfaceProfile()
        msg, d = tool_unlock_capability(p, "mind_control")
        self.assertIn("rejected", msg)
        self.assertEqual(p.unlocked, [])

    def test_emphasize_tool(self):
        p = InterfaceProfile()
        msg, d = tool_emphasize(p, "Hello there")
        self.assertIn("applied", msg)
        self.assertEqual(d["text"], "Hello there")


class TestToolSpecs(unittest.TestCase):
    def test_four_tools_well_formed(self):
        self.assertEqual(len(INTERFACE_TOOLS), 4)
        for spec in INTERFACE_TOOLS:
            self.assertIsNotNone(spec.name)
            self.assertIn("properties", spec.input_schema)

    def test_enums_match_constants(self):
        cap_spec = next(s for s in INTERFACE_TOOLS if s.name == "unlock_capability")
        self.assertEqual(set(cap_spec.input_schema["properties"]["capability"]["enum"]), set(CAPABILITIES))
        type_spec = next(s for s in INTERFACE_TOOLS if s.name == "set_type")
        self.assertEqual(set(type_spec.input_schema["properties"]["register"]["enum"]), set(TYPE_REGISTERS))


if __name__ == "__main__":
    unittest.main()
