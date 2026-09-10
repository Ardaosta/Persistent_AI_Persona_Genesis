"""Do the file paths written inside vault documents resolve?

The case this exists for: an authored persona doc pointed at
`relationship_questions.md` while the vault had slugged the file to
`relationship-questions.md`. Every read was a file-not-found, the error was
swallowed, and a get-to-know-you drip stayed dead for five days with no symptom
but silence.
"""

import tempfile
import unittest
from pathlib import Path

from genesis_memory import filerefs


class RefsCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, rel: str, body: str) -> Path:
        p = self.vault / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
        return p


class TestTheFiveDaySilence(RefsCase):
    def test_underscore_against_hyphen_is_caught_as_drift(self):
        self.write("soul/persona.md", "Work through `relationship_questions.md` slowly.")
        self.write("soul/relationship-questions.md", "# the questions")
        r = filerefs.lint(self.vault)
        self.assertEqual(len(r["missing"]), 0, "the file IS there, just spelled differently")
        self.assertEqual(len(r["drift"]), 1)
        self.assertEqual(r["drift"][0]["ref"], "relationship_questions.md")
        self.assertEqual(r["drift"][0]["suggestion"], "soul/relationship-questions.md")

    def test_a_genuinely_absent_file_is_missing_not_drift(self):
        self.write("soul/persona.md", "Notes go in findings/daily_notes.md.")
        r = filerefs.lint(self.vault)
        self.assertEqual(len(r["drift"]), 0)
        self.assertEqual([e["ref"] for e in r["missing"]], ["findings/daily_notes.md"])

    def test_the_report_names_the_document_at_fault(self):
        self.write("soul/persona.md", "See relationship_questions.md")
        self.write("soul/relationship-questions.md", "# q")
        text = filerefs.render(filerefs.lint(self.vault))
        self.assertIn("soul/persona.md", text)
        self.assertIn("soul/relationship-questions.md", text)


class TestItDoesNotCryWolf(RefsCase):
    """A check that fails on healthy vaults gets ignored, and then it is not a check."""

    def test_a_healthy_vault_passes_clean(self):
        self.write("soul/persona.md", "Work through soul/relationship-questions.md slowly.")
        self.write("soul/relationship-questions.md", "# the questions")
        r = filerefs.lint(self.vault)
        self.assertEqual(r["missing"], [])
        self.assertEqual(r["drift"], [])
        self.assertGreater(r["checked"], 0, "a pass on zero refs checked would prove nothing")

    def test_reference_resolves_relative_to_its_own_document(self):
        self.write("soul/persona.md", "See relationship-questions.md")
        self.write("soul/relationship-questions.md", "# q")
        r = filerefs.lint(self.vault)
        self.assertEqual(r["missing"] + r["drift"], [])

    def test_reference_resolves_from_the_vault_root_too(self):
        self.write("soul/persona.md", "See journal/2026-01-01.md")
        self.write("journal/2026-01-01.md", "# entry")
        r = filerefs.lint(self.vault)
        self.assertEqual(r["missing"] + r["drift"], [])

    def test_urls_are_not_vault_paths(self):
        # Locks the behavior the regex lookbehind provides. If someone later
        # loosens that anchor, this fails instead of the check going noisy.
        self.write("soul/persona.md", "Read https://example.com/guide.md for context.")
        r = filerefs.lint(self.vault)
        self.assertEqual(r["missing"] + r["drift"], [])

    def test_wikilinks_are_left_to_the_graph(self):
        self.write("soul/persona.md", "See [[some-other-fact]] about it.")
        r = filerefs.lint(self.vault)
        self.assertEqual(r["missing"] + r["drift"], [])

    def test_a_repeated_reference_is_reported_once(self):
        self.write("soul/persona.md", "gone.md and gone.md and gone.md again")
        r = filerefs.lint(self.vault)
        self.assertEqual(len(r["missing"]), 1)

    def test_an_empty_vault_is_not_an_error(self):
        r = filerefs.lint(self.vault)
        self.assertEqual((r["checked"], r["missing"], r["drift"]), (0, [], []))

    def test_a_missing_vault_directory_does_not_raise(self):
        r = filerefs.lint(self.vault / "nope")
        self.assertEqual(r["docs"], 0)


class TestNormalization(unittest.TestCase):
    def test_folds_the_drift_that_actually_happens(self):
        n = filerefs._norm_name
        self.assertEqual(n("relationship_questions.md"), n("relationship-questions.md"))
        self.assertEqual(n("Relationship Questions.MD"), n("relationship-questions.md"))

    def test_extension_is_part_of_identity(self):
        n = filerefs._norm_name
        self.assertNotEqual(n("notes.md"), n("notes.json"))


if __name__ == "__main__":
    unittest.main()
