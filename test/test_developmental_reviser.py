from __future__ import annotations

import unittest

from tools import developmental_reviser


class DevelopmentalReviserTests(unittest.TestCase):
    def test_normalize_plan_fills_missing_sections(self) -> None:
        plan = developmental_reviser.normalize_plan(
            {
                "premise": "A detective remembers every death.",
                "section_plans": [{"section": 2, "purpose": "Confront the broker."}],
            },
            3,
        )
        self.assertEqual(3, len(plan["section_plans"]))
        self.assertEqual(2, plan["section_plans"][1]["section"])
        self.assertIn("Preserve", plan["section_plans"][0]["purpose"])

    def test_validation_rejects_large_loss_and_model_preamble(self) -> None:
        source = "A consequential sentence. " * 300
        failures = developmental_reviser.validate_revision(source, "Here is the revision.")
        self.assertTrue(any(value.startswith("word_count_ratio_") for value in failures))
        self.assertIn("model_preamble", failures)

    def test_validation_accepts_bounded_clean_revision(self) -> None:
        source = "A consequential sentence about Maya. " * 300
        revised = "Maya makes one consequential choice. " * 300
        self.assertEqual([], developmental_reviser.validate_revision(source, revised))


if __name__ == "__main__":
    unittest.main()
