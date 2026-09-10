"""An escape hatch that permits zero without a floor becomes zero-always.

`should_stop` used to be satisfied the moment `next_question` returned None,
which on a starved or fully-rejected pool is true on the FIRST call. The
interview asked nothing, `finalize` returned a complete-looking all-zeros
profile, and `genesis status` reported it as tuned. The same week, a drip loop
authorized to "ask zero questions if nothing fits" asked zero forever.
"""

import unittest

from genesis_core import interview as iv


class TestTheFloorHolds(unittest.TestCase):
    def test_a_fresh_model_never_stops_at_zero(self):
        self.assertFalse(iv.should_stop(iv.UserModel()))

    def test_a_rejected_pool_used_to_end_the_interview_immediately(self):
        """The exact escape hatch. validate_question is a fail-closed guard, so a
        stricter guard or a bad pool edit reaches this state by design."""
        model = iv.UserModel()
        orig = iv.validate_question
        iv.validate_question = lambda q: False
        try:
            self.assertIsNone(iv.next_question(model), "precondition: no question available")
            # It still stops, because a pool that can serve nothing is a real dead
            # end. What must NOT happen is calling the result a tuning.
            self.assertTrue(iv.should_stop(model))
            out = iv.finalize(model)
            self.assertEqual(out["evidence"]["questions_asked"], 0)
            self.assertFalse(out["evidence"]["tuned"])
            self.assertTrue(out["evidence"]["starved"])
        finally:
            iv.validate_question = orig

    def test_early_confidence_does_not_beat_the_floor(self):
        """Two decisive answers can settle every axis. Confidence that cheap is
        exactly what the floor exists to distrust."""
        model = iv.UserModel()
        for axis in iv.AXES:
            model.scores[axis] = 1.0
            model.evidence[axis] = 1
        model.asked = ["q1", "q2"]
        self.assertTrue(model.confident(), "precondition: it thinks it is done")
        self.assertLess(len(model.asked), iv.MIN_QUESTIONS)
        self.assertFalse(iv.should_stop(model), "the floor outranks early confidence")

    def test_a_question_is_reachable_even_when_every_axis_settled(self):
        """next_question skips settled axes, so under the floor it returns None
        while good questions remain. Without this widening the floor is a number
        the loop can never reach."""
        model = iv.UserModel()
        for axis in iv.AXES:
            model.scores[axis] = 1.0
        model.asked = ["q1"]
        self.assertIsNone(iv.next_question(model))
        self.assertIsNotNone(iv.next_under_floor(model))

    def test_the_ceiling_still_wins_outright(self):
        model = iv.UserModel()
        model.asked = ["q%d" % i for i in range(iv.MAX_QUESTIONS)]
        self.assertTrue(iv.should_stop(model))

    def test_floor_sits_below_the_ceiling(self):
        self.assertLess(iv.MIN_QUESTIONS, iv.MAX_QUESTIONS)
        self.assertGreater(iv.MIN_QUESTIONS, 0)


class TestZeroIsRecordedRatherThanHidden(unittest.TestCase):
    def test_a_real_interview_reports_what_it_rests_on(self):
        model = iv.UserModel()
        pool = {q["id"]: q for q in iv.QUESTION_POOL}
        for qid in list(pool)[: iv.MIN_QUESTIONS]:
            model.apply(pool[qid], 1.0)
        ev = iv.finalize(model)["evidence"]
        self.assertEqual(ev["questions_asked"], iv.MIN_QUESTIONS)
        self.assertTrue(ev["tuned"])
        self.assertFalse(ev["starved"])

    def test_zero_and_six_are_no_longer_the_same_shape(self):
        """The heart of it: before this, an interview that asked nothing and one
        that asked six returned outputs a caller could not tell apart."""
        empty = iv.finalize(iv.UserModel())
        model = iv.UserModel()
        pool = {q["id"]: q for q in iv.QUESTION_POOL}
        for qid in list(pool)[: iv.MIN_QUESTIONS]:
            model.apply(pool[qid], 1.0)
        real = iv.finalize(model)
        self.assertNotEqual(empty["evidence"]["tuned"], real["evidence"]["tuned"])


if __name__ == "__main__":
    unittest.main()
