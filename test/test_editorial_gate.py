from __future__ import annotations

import unittest
from pathlib import Path
import tempfile

from tools import editorial_gate


class EditorialGateTests(unittest.TestCase):
    def test_bounded_excerpt_preserves_beginning_middle_and_end(self) -> None:
        source = "A" * 9_000 + "MIDDLE" + "Z" * 9_000
        excerpt = editorial_gate.bounded_excerpt(source, 6_000)
        self.assertLessEqual(len(excerpt), 6_200)
        self.assertTrue(excerpt.startswith("A" * 200))
        self.assertIn("MIDDLE", excerpt)
        self.assertIn("source continues outside this supplied window", excerpt)
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

    def test_normalizes_ten_point_model_scores_to_percentages(self) -> None:
        review = editorial_gate.normalize_chapter_review(
            {
                "coherence_score": 8,
                "prose_score": 7,
                "commercial_readiness_score": 6,
                "recommended_action": "revise",
            },
            1,
        )
        self.assertEqual(80, review["coherence_score"])
        self.assertEqual(70, review["prose_score"])
        self.assertEqual(60, review["commercial_readiness_score"])

    def test_reconciles_rejected_score_with_chapter_evidence(self) -> None:
        readiness = editorial_gate.reconcile_readiness(
            "reject",
            100,
            [{"commercial_readiness_score": 10}],
        )
        self.assertEqual(10, readiness)

    def test_caps_revise_score_below_release_ready(self) -> None:
        readiness = editorial_gate.reconcile_readiness(
            "revise",
            100,
            [{"commercial_readiness_score": 100}],
        )
        self.assertEqual(79, readiness)

    def test_parses_existing_source_override(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manuscript = Path(directory) / "candidate.md"
            manuscript.write_text("Candidate", encoding="utf-8")
            overrides = editorial_gate.parse_source_overrides(
                [f"trials-of-valor={manuscript}"]
            )
        self.assertEqual(manuscript.resolve(), overrides["trials-of-valor"])

    def test_rejects_malformed_source_override(self) -> None:
        with self.assertRaisesRegex(ValueError, "expected SLUG=PATH"):
            editorial_gate.parse_source_overrides(["missing-path"])


if __name__ == "__main__":
    unittest.main()
