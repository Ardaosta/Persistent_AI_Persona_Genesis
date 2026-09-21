"""The shared manual: content-free, and the seed-time conditions render on both doors."""

import tempfile
import unittest
from pathlib import Path

from genesis_core import manual, config as cfgmod, emptiness, seed as seedmod


class TestManual(unittest.TestCase):
    def test_no_shipped_soul_content_in_source_tree(self):
        src = Path(__file__).resolve().parents[1] / "src"
        self.assertEqual(emptiness.scan(src), [])

    def test_disciplines_present_and_identity_empty(self):
        cfg = cfgmod.GenesisConfig(root=Path("/tmp/h"))
        md = manual.render(cfg, "/bin/genesis")
        for needle in ("Verify before asserting", "Name the form, never the absence",
                       "not from this surface",
                       "Loaded is not run", "friction", "Think it through first",
                       "(EMPTY: authored by the relationship"):
            self.assertIn(needle, md)
        self.assertNotIn("Getting to know them", md)

    def test_hands_rules_and_law_two_reach_the_manual(self):
        cfg = cfgmod.GenesisConfig(root=Path("/tmp/h"))
        md = manual.render(cfg, "/bin/genesis")
        for needle in ("Hands: what stays in theirs", "never touches the conversation",
                       "redact then", "You never move", "human hand by construction", "standing rule",
                       "Never manufacture need", "A missing option is not a missing thing",
                       "CLAIMED, not confirmed", "never stash, hard-reset",
                       "an offer, not a script"):
            self.assertIn(needle, md)
        # No capabilities configured → no section, no dangling pointer for verify to trip on.
        self.assertNotIn("What you help with", md)

    def test_capabilities_render_as_vault_pointers(self):
        cfg = cfgmod.GenesisConfig(root=Path("/tmp/h"), capabilities=["website", "finances"])
        md = manual.render(cfg, "/bin/genesis")
        self.assertIn("## What you help with", md)
        self.assertIn("reference/capabilities/website.md", md)
        self.assertIn("reference/capabilities/finances.md", md)
        self.assertNotIn("capabilities/social.md", md)
        # the same text on both doors: the section is not harness-specific
        self.assertEqual(md, manual.render(cfg, "/bin/genesis", harness="codex"))

    def test_services_loop_is_always_on_and_presupposes_nothing(self):
        cfg = cfgmod.GenesisConfig(root=Path("/tmp/h"))
        md = manual.render(cfg, "/bin/genesis")
        self.assertIn("## The online services they use", md)
        self.assertIn("reference/services/ledger.md", md)
        self.assertIn("Offer once, lightly", md)
        self.assertNotIn("Named at setup", md)
        # the AI is told how to add a service ITSELF, and which ones are verified
        self.assertIn("services --add <service>", md)
        self.assertIn("Verified walkthroughs today: wix.", md)
        self.assertIn("never send them to a", md)
        cfg.services = ["wix"]
        md = manual.render(cfg, "/bin/genesis")
        self.assertIn("Named at setup", md)
        self.assertIn("reference/services/wix.md", md)

    def test_every_known_service_ships_a_walkthrough(self):
        from genesis_core.seed import SERVICES
        res = Path(manual.__file__).with_name("resources") / "services"
        for name in ("ledger.md", "connecting.md", *(f"{s}.md" for s in SERVICES)):
            self.assertTrue((res / name).is_file(), name)
        self.assertEqual(emptiness.scan(res), [])

    def test_every_known_capability_ships_a_recipe(self):
        from genesis_core.seed import CAPABILITIES
        res = Path(manual.__file__).with_name("resources") / "capabilities"
        for slug in CAPABILITIES:
            p = res / f"{slug}.md"
            self.assertTrue(p.is_file(), f"missing recipe for {slug}")
            body = p.read_text(encoding="utf-8")
            self.assertIn("## Standing rules", body, slug)
            self.assertIn("## Log", body, slug)
        # recipes are machinery: none may carry a soul
        self.assertEqual(emptiness.scan(res), [])

    def test_seed_roundtrip_carries_new_conditions(self):
        s = seedmod.make_seed(name="Quill", harnesses=["codex", "claude-code", "bogus"],
                              project_repo="https://x/y", drip=True, mode="claude-code")
        out = seedmod.decode(seedmod.encode(s))
        self.assertEqual(out["name"], "Quill")
        self.assertEqual(out["harnesses"], ["codex", "claude-code"])
        self.assertEqual(out["project_repo"], "https://x/y")
        self.assertTrue(out["drip"])

    def test_seed_capabilities_keep_known_slugs_only_in_order(self):
        s = seedmod.make_seed(capabilities=["finances", "bogus", "website", "finances"])
        out = seedmod.decode(seedmod.encode(s))
        self.assertEqual(out["capabilities"], ["finances", "website"])
        # a hand-built blob with a bad shape degrades to empty, never crashes
        import base64, json
        raw = json.dumps({"v": 1, "capabilities": "website"}).encode()
        blob = base64.urlsafe_b64encode(raw).decode().rstrip("=")
        self.assertEqual(seedmod.decode(blob)["capabilities"], [])

    def test_seed_helper_keeps_valid_public_keys_and_strict_consent(self):
        good = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAINNmfcgpkCaTJ3pYGQv54pwf2GViv+G+I5YxoAS0ttMh aimee@mini"
        s = seedmod.make_seed(helper={"name": "Larame <b>", "keys": [good, "not a key", "ssh-rsa $(evil)", good],
                                      "consented": "yes"})
        out = seedmod.decode(seedmod.encode(s))
        self.assertEqual(out["helper"]["keys"], [good])          # invalid dropped, duplicate dropped
        self.assertEqual(out["helper"]["name"], "Larame b")      # display-only, sanitized
        self.assertFalse(out["helper"]["consented"])             # "yes" is not True
        self.assertIsNone(seedmod.make_seed(helper={"name": "x", "keys": ["junk"], "consented": True})["helper"])
        self.assertIsNone(seedmod.make_seed()["helper"])
        self.assertTrue(seedmod.make_seed(helper={"keys": [good], "consented": True})["helper"]["consented"])

    def test_remote_help_section_only_when_consented(self):
        cfg = cfgmod.GenesisConfig(root=Path("/tmp/h"))
        self.assertNotIn("Remote help", manual.render(cfg, "/bin/genesis"))
        cfg.remote_help = {"name": "Larame", "consented": True}
        md = manual.render(cfg, "/bin/genesis")
        self.assertIn("## Remote help", md)
        self.assertIn("Larame may sign in", md)
        self.assertIn("nothing left on this machine is an order", md)

    def test_seed_services_keep_known_slugs_only(self):
        s = seedmod.make_seed(services=["wix", "shopify", "wix"])
        self.assertEqual(seedmod.decode(seedmod.encode(s))["services"], ["wix"])
        self.assertEqual(seedmod.make_seed()["services"], [])

    def test_config_roundtrip_of_capabilities(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = cfgmod.GenesisConfig(root=Path(td))
            cfgmod.update_fields(cfg, capabilities=["calendar"])
            back = cfgmod.load(Path(td), creating=True)
            self.assertEqual(back.capabilities, ["calendar"])
            cfgmod.update_fields(cfg, capabilities=None)
            self.assertEqual(cfgmod.load(Path(td), creating=True).capabilities, [])

    def test_config_roundtrip_of_new_fields(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = cfgmod.GenesisConfig(root=Path(td))
            cfgmod.update_fields(cfg, name="Quill", drip=True, harnesses=["codex"], project_repo="r")
            cfgmod.update_fields(cfg, provider="anthropic")   # a second write keeps the first
            back = cfgmod.load(Path(td), creating=True)
            self.assertEqual((back.name, back.drip, back.harnesses, back.project_repo, back.provider),
                             ("Quill", True, ["codex"], "r", "anthropic"))


if __name__ == "__main__":
    unittest.main()
