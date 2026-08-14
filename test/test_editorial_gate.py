from __future__ import annotations

import unittest

from tools import editorial_gate


class EditorialGateTests(unittest.TestCase):
    def test_bounded_excerpt_preserves_beginning_middle_and_end(self) -> None:
        source = "A" * 9_000 + "MIDDLE" + "Z" * 9_000
        excerpt = editorial_gate.bounded_excerpt(source, 6_000)
        self.assertLessEqual(len(excerpt), 6_200)
        self.assertTrue(excerpt.startswith("A" * 200))
        self.assertIn("MIDDLE", excerpt)
        self.assertTrue(excerpt.endswith("Z" * 200))

    def test_normalizes_invalid_model_decision_and_scores(self) -> None:
        review = editorial_gate.normalize_chapter_review(
            {
                "coherence_score": 120,
                "prose_score": "72",
                "commercial_readiness_score": -5,
                "strengths": ["Hook"],
                "blocking_defects": ["False ending"],
                "continuity_notes": [],
                "recommended_action": "celebrate",
            },
            3,
        )
        self.assertEqual(100, review["coherence_score"])
        self.assertEqual(72, review["prose_score"])
        self.assertEqual(0, review["commercial_readiness_score"])
        self.assertEqual("revise", review["recommended_action"])


if __name__ == "__main__":
    unittest.main()
