import json
import unittest

from tests.eval_paths import find_evals_file


class EvalSetArtifactTests(unittest.TestCase):
    def test_offline_eval_set_exists_and_has_minimum_questions(self) -> None:
        path = find_evals_file("offline_eval_set.jsonl")
        if path is None:
            self.skipTest("docs/evals/offline_eval_set.jsonl not found (run from repo checkout)")
        lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        self.assertGreaterEqual(len(lines), 30)
        for ln in lines:
            obj = json.loads(ln)
            self.assertIn("id", obj)
            self.assertIn("question", obj)
            self.assertIn("intent", obj)


if __name__ == "__main__":
    unittest.main()
