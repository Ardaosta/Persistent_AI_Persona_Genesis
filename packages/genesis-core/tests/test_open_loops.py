"""Open loops wired through the agent: the tool, the boot slot, the manual, and
the drip-bank fork that rides on the onboarding's tool/companion answer."""

import re
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from genesis_memory import OpenLoops, Vault
from genesis_core import boot, emptiness, interview, manual, config as cfgmod
from genesis_core.agent import _MEMORY_TOOLS, dispatch
from genesis_core.mcp_server import tools_payload


def _cfg(root: Path, **kw) -> cfgmod.GenesisConfig:
    # A private engine, so the privacy gate is not what these tests exercise.
    return cfgmod.GenesisConfig(root=root, trains=False, **kw)


class TestOpenLoopsTool(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = _cfg(Path(self.tmp.name))
        self.cfg.vault_dir.mkdir(parents=True, exist_ok=True)
        self.vault = Vault(self.cfg.vault_dir)

    def tearDown(self):
        self.tmp.cleanup()

    def call(self, **args):
        return dispatch({"tool": "open_loops", "args": args}, self.vault, self.cfg)

    def test_tool_is_offered_to_every_door(self):
        self.assertIn("open_loops", [t.name for t in _MEMORY_TOOLS])
        self.assertIn("open_loops", [t["name"] for t in tools_payload()])

    def test_add_list_asked_close_round_trip(self):
        self.assertIn("saved", self.call(action="add", id="pr-12", title="Merge the site map PR",
                                         ball="them"))
        self.assertIn("pr-12", self.call(action="list"))
        self.assertIn("snoozed", self.call(action="asked", id="pr-12", answer="Friday"))
        self.assertIn("closed", self.call(action="close", id="pr-12", note="merged"))
        self.assertEqual(self.call(action="list"), "no open loops")

    def test_empty_title_is_an_error_not_a_placeholder(self):
        self.assertTrue(self.call(action="add", id="x", title="").startswith("error"))
        self.assertEqual(OpenLoops(self.cfg.vault_dir).open(), [])

    def test_bad_action_is_an_error(self):
        self.assertTrue(self.call(action="nope").startswith("error"))

    def test_training_engine_writes_nothing(self):
        cfg = cfgmod.GenesisConfig(root=self.cfg.root, trains=True)
        out = dispatch({"tool": "open_loops", "args": {"action": "add", "id": "a", "title": "t"}},
                       self.vault, cfg)
        self.assertTrue(out.startswith("not saved"))
        self.assertEqual(OpenLoops(self.cfg.vault_dir).open(), [])


class TestBootSlot(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = _cfg(Path(self.tmp.name))
        self.cfg.vault_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_due_loop_reaches_boot_context_whatever_the_continuity_tail(self):
        """The failure this replaces: a follow-up reached its companion only
        because it happened to be the newest continuity entry."""
        long_ago = date.today() - timedelta(days=30)
        OpenLoops(self.cfg.vault_dir).add("site-visit", "Ask how the site visit went", today=long_ago)
        from genesis_memory import Continuity
        c = Continuity(self.cfg.vault_dir)
        for i in range(20):
            c.append(f"an unrelated reflection number {i} " * 20)
        text = boot.boot_context_text(self.cfg)
        self.assertIn("## Open loops", text)
        self.assertIn("Ask how the site visit went", text)

    def test_no_loops_no_block(self):
        self.assertNotIn("## Open loops", boot.boot_context_text(self.cfg))

    def test_corrupt_list_is_said_out_loud(self):
        (self.cfg.vault_dir / "open-loops.json").write_text("{broken", encoding="utf-8")
        self.assertIn("could not read your open loops", boot.open_loops_block(self.cfg))


class TestManualAndBankFork(unittest.TestCase):
    def test_every_manual_carries_open_loops(self):
        md = manual.render(cfgmod.GenesisConfig(root=Path("/tmp/h")), "/bin/genesis")
        self.assertIn("## Open loops", md)
        self.assertIn('"/bin/genesis" loops', md)

    def test_bank_follows_the_onboarding_answer(self):
        tool = cfgmod.GenesisConfig(root=Path("/tmp/h"), drip=True,
                                    machinery={"question_bank": "working"})
        comp = cfgmod.GenesisConfig(root=Path("/tmp/h"), drip=True,
                                    machinery={"question_bank": "relationship"})
        old = cfgmod.GenesisConfig(root=Path("/tmp/h"), drip=True, machinery={})
        self.assertIn("working-questions.md", manual.render(tool, "/bin/genesis"))
        self.assertIn("relationship-questions.md", manual.render(comp, "/bin/genesis"))
        # every agent onboarded before the fork keeps exactly what it had
        self.assertIn("relationship-questions.md", manual.render(old, "/bin/genesis"))

    def test_both_banks_ship_and_carry_no_soul(self):
        res = Path(manual.__file__).with_name("resources")
        for name in ("relationship_questions.md", "working_questions.md"):
            self.assertTrue((res / name).is_file(), name)
        self.assertEqual(emptiness.scan(res / "working_questions.md"), [])

    def test_working_bank_skips_the_personal_waves(self):
        text = (Path(manual.__file__).with_name("resources") / "working_questions.md").read_text()
        self.assertNotIn("when you were ten", text)
        self.assertNotIn("What do you want me to want", text)
        self.assertIn("follow up", text)

    def test_finalize_forks_on_tool_companion(self):
        m = interview.UserModel()
        m.scores["tool_companion"] = -0.8
        self.assertEqual(interview.finalize(m)["machinery"]["question_bank"], "working")
        m.scores["tool_companion"] = 0.8
        self.assertEqual(interview.finalize(m)["machinery"]["question_bank"], "relationship")

    def test_web_interview_uses_the_same_threshold(self):
        ts = Path(__file__).resolve().parents[3] / "web" / "lib" / "interview.ts"
        if not ts.is_file():
            self.skipTest("web/ not present in this checkout")
        self.assertRegex(ts.read_text(), re.compile(
            r'question_bank:\s*tc\s*>=\s*0\.2\s*\?\s*"relationship"\s*:\s*"working"'))


if __name__ == "__main__":
    unittest.main()
