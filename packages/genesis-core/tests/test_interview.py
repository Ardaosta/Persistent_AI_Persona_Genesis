"""Tests for the adaptive interview v2: guards, graded selection, continuum out."""

import unittest

from genesis_core.interview import (
    AXES,
    QUESTION_POOL,
    UserModel,
    finalize,
    next_question,
    should_stop,
    validate_question,
)


class TestGuards(unittest.TestCase):
    def test_vetted_pool_all_pass(self):
        for q in QUESTION_POOL:
            self.assertTrue(validate_question(q), f"vetted question failed guards: {q['id']}")

    def test_character_defining_question_rejected(self):
        for bad in [
            {"axis": "tool_companion", "prompt": "How warm and funny should your AI be?", "choices": []},
            {"axis": "tool_companion", "prompt": "Do you want it to flirt with you?", "choices": []},
            {"axis": "tool_companion", "prompt": "What personality should it have?", "choices": []},
            {"axis": "tool_companion", "prompt": "Pick its tone:", "choices": [{"label": "warm and affectionate"}]},
        ]:
            self.assertFalse(validate_question(bad), f"should reject: {bad['prompt']}")

    def test_boundary_register_question_rejected(self):
        bad = {"axis": "tool_companion", "prompt": "Share your politics and religion?", "choices": []}
        self.assertFalse(validate_question(bad))

    def test_disallowed_axis_rejected(self):
        bad = {"axis": "warmth_level", "prompt": "How often should it praise you?", "choices": []}
        self.assertFalse(validate_question(bad))


class TestSelectionAndModel(unittest.TestCase):
    def test_decisive_answer_settles_axis(self):
        m = UserModel()
        q1 = next_question(m)
        m.apply(q1, 1)  # decisive
        self.assertTrue(m.settled(q1["axis"]))
        q2 = next_question(m)
        self.assertNotEqual(q1["axis"], q2["axis"])

    def test_no_repeat_questions(self):
        m = UserModel()
        seen = set()
        while not should_stop(m):
            q = next_question(m)
            if q is None:
                break
            self.assertNotIn(q["id"], seen)
            seen.add(q["id"])
            m.apply(q, 1)

    def test_clear_user_terminates_early(self):
        m = UserModel()
        steps = 0
        while not should_stop(m):
            m.apply(next_question(m), 1)
            steps += 1
        self.assertEqual(steps, 4)  # one decisive answer per axis

    def test_mild_answer_triggers_refiner(self):
        # a mild ("occasional nudge") answer leaves tool_companion unsettled, so its
        # refiner (whenithas) should fire to place the user more precisely.
        m = UserModel()
        decisive = {"turnkey_tinkerer": -1, "narrow_broad": 1, "voice_text": 1}
        while not should_stop(m):
            q = next_question(m)
            if q is None:
                break
            sig = 0.4 if (q["axis"] == "tool_companion" and "whenithas" not in m.asked) else decisive.get(q["axis"], 1)
            m.apply(q, sig)
        self.assertIn("whenithas", m.asked)

    def test_ambiguous_axis_without_refiner_stops(self):
        # neutral on modality (no second voice/text question) → stop, don't pad.
        m = UserModel()
        answers = {"tool_companion": 1, "turnkey_tinkerer": -1, "narrow_broad": 1, "voice_text": 0}
        while not should_stop(m):
            q = next_question(m)
            if q is None:
                break
            m.apply(q, answers[q["axis"]])
        self.assertEqual(len(m.asked), 4)
        self.assertNotIn("whenithas", m.asked)


class TestContinuumOutput(unittest.TestCase):
    def test_positions_are_continuous(self):
        m = UserModel()
        m.scores["tool_companion"] = 0.4   # a lean, not a pole
        out = finalize(m)
        self.assertEqual(out["archetype"]["positions"]["tool_companion"], 0.4)
        self.assertEqual(out["archetype"]["relationship"], "leans companion")
        self.assertEqual(out["archetype"]["confidence"]["tool_companion"], "medium")

    def test_machinery_tuned_by_degree(self):
        # a mild companion lean → "occasional" proactivity, not full "active"
        m = UserModel()
        m.scores["tool_companion"] = 0.4
        self.assertEqual(finalize(m)["machinery"]["proactivity"], "occasional")
        m.scores["tool_companion"] = 1.0
        self.assertEqual(finalize(m)["machinery"]["proactivity"], "active")
        m.scores["tool_companion"] = -1.0
        self.assertEqual(finalize(m)["machinery"]["proactivity"], "on_request")

    def test_no_disposition_in_machinery(self):
        m = UserModel()
        for a in AXES:
            m.scores[a] = 1.0
        out = finalize(m)
        for forbidden in ("warmth", "register", "personality", "tone", "honesty"):
            self.assertNotIn(forbidden, out["machinery"])

    def test_unsure_user(self):
        out = finalize(UserModel())
        self.assertEqual(out["archetype"]["relationship"], "unsure")
        self.assertEqual(out["machinery"]["autonomy"], "ask_when_unsure")


if __name__ == "__main__":
    unittest.main()
