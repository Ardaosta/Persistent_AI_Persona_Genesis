"""Not "is it stored" but "can it be found".

From measuring a real store: the documents that DEFINED behavior were the ones
too long to be recalled by meaning, 28% of the store was orphaned, and an
always-loaded index once collapsed to the last N filenames alphabetically. A
personality-defining memory can be dropped by an alphabet.
"""

import tempfile
import unittest
from pathlib import Path

from genesis_memory import Fact, Vault, reachability as reach


def fact(fid, desc="a description long enough to carry a real retrieval trigger",
         body="short", kind="project"):
    return Fact(id=fid, kind=kind, description=desc, body=body)


class TestLengthInvertsIntent(unittest.TestCase):
    """The more carefully a document is written, the less of it is findable."""

    def test_a_document_past_the_window_is_partly_unreachable(self):
        f = fact("design-plan", body="x" * (4 * 4096))
        c = reach.chunk_coverage(f, chunk_tokens=2048)
        self.assertTrue(c["over_window"])
        self.assertLess(c["reachable_pct"], 100.0)

    def test_a_short_document_is_fully_reachable(self):
        c = reach.chunk_coverage(fact("small", body="a paragraph"), chunk_tokens=2048)
        self.assertFalse(c["over_window"])
        self.assertEqual(c["reachable_pct"], 100.0)

    def test_a_bigger_window_is_the_other_real_fix(self):
        f = fact("design-plan", body="x" * (4 * 4096))
        self.assertTrue(reach.chunk_coverage(f, 2048)["over_window"])
        self.assertFalse(reach.chunk_coverage(f, 8192)["over_window"])


class TestOrphans(unittest.TestCase):
    def test_a_fact_nothing_links_is_an_orphan(self):
        facts = [fact("alone", body="no links here"),
                 fact("a", body="see [[b]]"), fact("b", body="see [[a]]")]
        self.assertEqual(reach.orphans(facts), ["alone"])

    def test_an_inbound_link_is_enough_to_not_be_orphaned(self):
        facts = [fact("target", body="nothing outbound"), fact("source", body="see [[target]]")]
        self.assertEqual(reach.orphans(facts), [])


class TestDescriptionsAreTriggersNotSummaries(unittest.TestCase):
    def test_a_description_restating_the_id_is_flagged(self):
        problems = reach.description_quality(fact("design-plan", desc="design plan"))
        self.assertTrue(any("restates the id" in p for p in problems))

    def test_a_too_thin_description_is_flagged(self):
        self.assertTrue(reach.description_quality(fact("x-y", desc="The plan")))

    def test_a_real_trigger_passes(self):
        f = fact("design-plan",
                 desc="two repos, private dev against public mirror, verify the scrub before push")
        self.assertEqual(reach.description_quality(f), [])


class TestTheIndexBudget(unittest.TestCase):
    def test_a_comfortable_index_is_not_over_budget(self):
        r = reach.report([fact("a"), fact("b")])
        self.assertFalse(r["index_over_budget"])

    def test_an_overflowing_index_is_named_rather_than_left_silent(self):
        """enforce_budget never DROPS an entry, which is the guarantee that
        matters. But with every description at the floor it returns text over
        the cap, and nothing downstream refuses it."""
        facts = [fact(f"fact-{i:04d}") for i in range(400)]
        r = reach.report(facts, max_bytes=2000)
        self.assertTrue(r["index_over_budget"])
        self.assertIn("OVER BUDGET", reach.render(r))

    def test_clipped_descriptions_are_reported(self):
        facts = [fact(f"fact-{i:03d}", desc="a long description " * 8) for i in range(40)]
        r = reach.report(facts, max_bytes=3000)
        self.assertTrue(r["clipped_descriptions"])


class TestWriteTimeWarnings(unittest.TestCase):
    """Told at write time it is an edit. Discovered six weeks later it is
    archaeology, and the document was unfindable the whole time."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.vault = Vault(Path(self._tmp.name))

    def tearDown(self):
        self._tmp.cleanup()

    def test_the_blessed_write_path_warns_about_a_long_body(self):
        notes = []
        self.vault.write(fact("big", body="x" * (4 * 4096)), warn=notes.append)
        # asserted on substance, not on the exact sentence, so rewording the
        # message does not fail a test about behavior
        self.assertTrue(notes)
        self.assertTrue(any("token" in n and "window" in n for n in notes))

    def test_it_warns_but_never_refuses(self):
        """Refusing would lose the thought, which is worse than a thought that
        is hard to search for."""
        path = self.vault.write(fact("big", desc="big", body="x" * (4 * 4096)), warn=lambda n: None)
        self.assertTrue(path.is_file())

    def test_a_good_fact_produces_no_noise(self):
        notes = []
        self.vault.write(fact("fine"), warn=notes.append)
        self.assertEqual(notes, [])

    def test_warn_is_optional_and_the_old_signature_still_works(self):
        self.assertTrue(self.vault.write(fact("nowarn")).is_file())


class TestOneBadFileIsNotADeadVault(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.vault = Vault(self.root)

    def tearDown(self):
        self._tmp.cleanup()

    def test_an_unparseable_file_is_skipped_not_raised(self):
        """The vault is plain markdown on the person's own machine and they are
        invited to open it, so a hand-edited file with an illegal name is an
        ordinary Tuesday. It used to take down every read path with a traceback."""
        self.vault.write(fact("good-one"))
        (self.root / "project" / "bad name.md").write_text(
            "---\nid: bad name\nkind: project\ndescription: x\n---\nbody\n", encoding="utf-8")
        bad = []
        facts = list(self.vault.iter_facts(on_error=lambda p, e: bad.append(p.name)))
        self.assertEqual([f.id for f in facts], ["good-one"])
        self.assertEqual(bad, ["bad name.md"])

    def test_unreadable_files_are_named_in_the_report(self):
        r = reach.report([fact("a")], unreadable=["bad name.md: invalid slug"])
        self.assertIn("UNREADABLE", reach.render(r))
        self.assertIn("bad name.md", reach.render(r))


if __name__ == "__main__":
    unittest.main()
