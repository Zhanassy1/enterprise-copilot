import json
import unittest
from pathlib import Path


class EvalSetArtifactTests(unittest.TestCase):
    def test_offline_eval_set_exists_and_has_minimum_questions(self) -> None:
        path = Path(__file__).resolve().parents[2] / "docs" / "evals" / "offline_eval_set.jsonl"
        self.assertTrue(path.exists(), "offline eval set file is required")
        lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        self.assertGreaterEqual(len(lines), 30)
        for ln in lines:
            obj = json.loads(ln)
            self.assertIn("id", obj)
            self.assertIn("question", obj)
            self.assertIn("intent", obj)


if __name__ == "__main__":
    unittest.main()
