import unittest
from pathlib import Path


class WorkspaceMigrationSmokeTests(unittest.TestCase):
    def test_phase1_migration_exists(self) -> None:
        migration_path = (
            Path(__file__).resolve().parents[1]
            / "alembic"
            / "versions"
            / "20260328_0003_phase1_workspace_foundation.py"
        )
        self.assertTrue(migration_path.exists(), "Phase 1 migration file must exist")

    def test_migration_contains_workspace_backfill(self) -> None:
        migration_path = (
            Path(__file__).resolve().parents[1]
            / "alembic"
            / "versions"
            / "20260328_0003_phase1_workspace_foundation.py"
        )
        body = migration_path.read_text(encoding="utf-8")
        self.assertIn("UPDATE documents", body)
        self.assertIn("UPDATE chat_sessions", body)
        self.assertIn("INSERT INTO workspaces", body)
        self.assertIn("workspace_members", body)


if __name__ == "__main__":
    unittest.main()
