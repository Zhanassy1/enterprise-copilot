import json
import unittest

from app.core.config import settings
from app.services.nlp import decide_response_mode

from tests.eval_paths import find_evals_file


class RelevanceRegressionTests(unittest.TestCase):
    def test_regression_cases_decision_stability(self) -> None:
        path = find_evals_file("relevance_regression_cases.json")
        if path is None:
            self.skipTest("docs/evals/relevance_regression_cases.json not found (run from repo checkout)")
        cases = json.loads(path.read_text(encoding="utf-8"))
        for case in cases:
            with self.subTest(case_id=case["id"]):
                decision, _confidence = decide_response_mode(
                    case["query"],
                    case["hits"],
                    answer_threshold=settings.answer_threshold,
                    clarify_threshold=settings.clarify_threshold,
                )
                self.assertEqual(decision, case["expected_decision"])


if __name__ == "__main__":
    unittest.main()
