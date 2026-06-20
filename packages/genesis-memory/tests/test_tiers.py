"""The three memory tiers and, above all, the no-leak invariant: perishable and
continuity must NEVER surface as durable facts."""

import tempfile
import unittest
from pathlib import Path

from genesis_memory import Continuity, Fact, Perishable, Vault
from genesis_memory.tiers import CONTINUITY_DIRNAME, PERISHABLE_DIRNAME


class TestPerishable(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.root = Path(self._td.name)

    def tearDown(self):
        self._td.cleanup()

    def test_write_read_overwrite(self):
        p = Perishable(self.root)
        p.write("first state")
        self.assertEqual(p.read(), "first state")
        p.write("second state")  # overwrite freely — the whole point
        self.assertEqual(p.read(), "second state")

    def test_named_slots(self):
        p = Perishable(self.root)
        p.write("a", slot="alpha")
        p.write("b", slot="beta")
        self.assertEqual(sorted(p.slots()), ["alpha", "beta"])
        self.assertEqual(p.read(slot="alpha"), "a")

    def test_clear(self):
        p = Perishable(self.root)
        p.write("x", slot="one")
        p.write("y", slot="two")
        p.clear(slot="one")
        self.assertEqual(p.slots(), ["two"])
        p.clear()  # all
        self.assertEqual(p.slots(), [])

    def test_bad_slot_rejected(self):
        p = Perishable(self.root)
        for bad in ("../escape", "a/b", ".hidden"):
            with self.assertRaises(ValueError):
                p.write("x", slot=bad)

    def test_lives_beside_vault_not_inside(self):
        p = Perishable(self.root)
        self.assertEqual(p.dir, self.root / PERISHABLE_DIRNAME)
        self.assertNotIn("vault", p.dir.parts[-2:])


class TestContinuity(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.vault_dir = Path(self._td.name) / "vault"

    def tearDown(self):
        self._td.cleanup()

    def test_append_only_never_rewrites(self):
        c = Continuity(self.vault_dir)
        c.append("I noticed something today.", now="2026-06-20T10:00:00+00:00")
        c.append("And something else later.", now="2026-06-20T18:00:00+00:00")
        text = c.read()
        self.assertIn("I noticed something today.", text)
        self.assertIn("And something else later.", text)
        # both stamps present → nothing was overwritten
        self.assertIn("2026-06-20T10:00:00+00:00", text)
        self.assertIn("2026-06-20T18:00:00+00:00", text)

    def test_empty_append_is_noop(self):
        c = Continuity(self.vault_dir)
        c.append("   ")
        self.assertEqual(c.read(), "")

    def test_tail(self):
        c = Continuity(self.vault_dir)
        c.append("x" * 2000)
        self.assertLessEqual(len(c.tail(500)), 500)

    def test_voice_sample_settable(self):
        c = Continuity(self.vault_dir)
        self.assertEqual(c.voice_sample(), "")
        c.set_voice_sample("This is how I sound.")
        self.assertEqual(c.voice_sample(), "This is how I sound.")

    def test_lives_inside_vault(self):
        c = Continuity(self.vault_dir)
        self.assertEqual(c.dir, self.vault_dir / CONTINUITY_DIRNAME)


class TestNoLeakInvariant(unittest.TestCase):
    """The load-bearing guarantee: neither perishable nor continuity content can
    ever be read back as a durable Fact."""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.root = Path(self._td.name)
        self.vault_dir = self.root / "vault"

    def tearDown(self):
        self._td.cleanup()

    def test_perishable_invisible_to_vault(self):
        Perishable(self.root).write("ephemeral handoff junk", slot="working_state")
        vault = Vault(self.vault_dir)
        ids = [f.id for f in vault.iter_facts()]
        self.assertEqual(ids, [])  # nothing perishable became a fact

    def test_continuity_invisible_to_vault(self):
        Continuity(self.vault_dir).append("raw first-person becoming")
        vault = Vault(self.vault_dir)
        # a real durable fact coexists, but continuity is not iterated as one
        vault.write(Fact(id="dog-vin", kind="user", description="has a wolfhound"))
        ids = [f.id for f in vault.iter_facts()]
        self.assertEqual(ids, ["dog-vin"])
        self.assertNotIn("thread", ids)

    def test_dir_names_are_not_fact_kinds(self):
        from genesis_memory import KINDS
        self.assertNotIn(PERISHABLE_DIRNAME, KINDS)
        self.assertNotIn(CONTINUITY_DIRNAME, KINDS)


if __name__ == "__main__":
    unittest.main()
