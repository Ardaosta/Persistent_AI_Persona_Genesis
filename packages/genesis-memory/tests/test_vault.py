import tempfile
import threading
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


class TestWriteDurability(unittest.TestCase):
    """Regressions for the two write-path bugs a sibling companion found on 2026-07-29 by
    reading vault.write() while answering a question about concurrent writers."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp())

    def test_created_survives_an_update(self):
        """agent.py's remember branch builds a FRESH Fact every call, always with
        created=None. The old code read that as 'brand new' and re-stamped
        created, so re-remembering an existing id silently erased the date the
        vault first learned the thing. Nothing errored; history just changed."""
        v = Vault(self.root)
        v.write(Fact(id="d1", kind="user", description="first", body="v1"), now="2020-01-01T00:00:00+00:00")
        # exactly the shape the agent sends on an update: no created, no history
        v.write(Fact(id="d1", kind="user", description="second", body="v2"), now="2026-07-29T00:00:00+00:00")
        got = v.get("d1")
        self.assertEqual(got.created, "2020-01-01T00:00:00+00:00")   # original date kept
        self.assertEqual(got.updated, "2026-07-29T00:00:00+00:00")   # update stamped
        self.assertEqual(got.body, "v2")

    def test_explicit_created_still_wins(self):
        """Preserving on-disk created must not override a caller who supplied one
        (migrations and imports carry their own dates)."""
        v = Vault(self.root)
        v.write(Fact(id="d2", kind="user", description="x", body="b"), now="2026-01-01T00:00:00+00:00")
        f = Fact(id="d2", kind="user", description="x", body="b")
        f.created = "1999-12-31T00:00:00+00:00"
        v.write(f, now="2026-07-29T00:00:00+00:00")
        self.assertEqual(v.get("d2").created, "1999-12-31T00:00:00+00:00")

    def test_no_temp_files_left_behind(self):
        v = Vault(self.root)
        v.write(Fact(id="d3", kind="user", description="x", body="b"))
        self.assertEqual(list(self.root.rglob(".*tmp")), [])

    def test_concurrent_writes_to_different_facts_all_land(self):
        v = Vault(self.root)
        errs = []
        def w(i):
            try:
                v.write(Fact(id=f"c{i}", kind="reference", description=f"f{i}", body="x" * 4000))
            except Exception as e:  # noqa: BLE001
                errs.append(e)
        ts = [threading.Thread(target=w, args=(i,)) for i in range(24)]
        for t in ts: t.start()
        for t in ts: t.join()
        self.assertEqual(errs, [])
        self.assertEqual(len(list((self.root / "reference").glob("*.md"))), 24)
        self.assertEqual(list(self.root.rglob(".*tmp")), [])

    def test_same_id_race_never_tears_the_file(self):
        """The old bare write_text truncated then filled, so two writers to one id
        could interleave into an unparseable file and a concurrent reader could
        catch a partial. With temp+os.replace the worst case is clean
        last-writer-wins."""
        v = Vault(self.root)
        errs = []
        def w(n):
            try:
                v.write(Fact(id="hot", kind="project", description=f"writer {n}", body="y" * 8000))
            except Exception as e:  # noqa: BLE001
                errs.append(e)
        ts = [threading.Thread(target=w, args=(i,)) for i in range(16)]
        for t in ts: t.start()
        for t in ts: t.join()
        self.assertEqual(errs, [])
        got = v.get("hot")                                  # parses at all
        self.assertTrue(got.description.startswith("writer"))
        self.assertEqual(len(got.body), 8000)               # one whole body, not a splice


if __name__ == "__main__":
    unittest.main()
