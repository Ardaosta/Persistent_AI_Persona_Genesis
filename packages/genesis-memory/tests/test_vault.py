import tempfile
import unittest
from pathlib import Path

from genesis_memory import Fact, FactError, Vault

_T = "2026-06-18T00:00:00+00:00"


class TestVault(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_write_read_roundtrip(self):
        v = Vault(self.root)
        path = v.write(Fact(id="larame", kind="user", description="the human", body="Lives in Longmont."), now=_T)
        self.assertEqual(path, self.root / "user" / "larame.md")
        got = v.read(path)
        self.assertEqual(got.id, "larame")
        self.assertEqual(got.description, "the human")
        self.assertEqual(got.body, "Lives in Longmont.")
        self.assertEqual(got.created, _T)

    def test_iter_and_get(self):
        v = Vault(self.root)
        v.write(Fact(id="a", kind="user", description="A"), now=_T)
        v.write(Fact(id="b", kind="soul", description="B"), now=_T)
        self.assertEqual({f.id for f in v.iter_facts()}, {"a", "b"})
        self.assertEqual(v.get("b").kind, "soul")
        self.assertIsNone(v.get("missing"))

    def test_extra_frontmatter_preserved(self):
        v = Vault(self.root)
        v.write(Fact(id="s", kind="soul", description="self note", extra={"reassembly_priority": "5"}), now=_T)
        self.assertEqual(v.get("s").extra.get("reassembly_priority"), "5")

    def test_schema_enforced(self):
        with self.assertRaises(FactError):
            Fact(id="_private", kind="user", description="reserved slug")
        with self.assertRaises(FactError):
            Fact(id="ok", kind="not-a-kind", description="bad kind")

    def test_messy_description_round_trips_without_corruption(self):
        # the two verified bugs together: newlines + markdown-breaking brackets
        v = Vault(self.root)
        messy = "loves ] brackets ) and (parens\nand a second line: with colons"
        v.write(Fact(id="t3", kind="user", description=messy, body="multi\nline\nbody"), now=_T)
        got = v.get("t3")
        self.assertNotIn("\n", got.description)            # folded, not orphaned
        self.assertIn("brackets", got.description)
        self.assertIn("second line", got.description)      # nothing lost on read-back
        self.assertEqual(got.body, "multi\nline\nbody")    # body keeps its newlines


if __name__ == "__main__":
    unittest.main()
