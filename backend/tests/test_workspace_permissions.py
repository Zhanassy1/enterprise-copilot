import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from app.api.deps import WorkspaceContext, get_workspace_context, require_roles


class WorkspacePermissionTests(unittest.TestCase):
    def _ctx(self, role_name: str) -> WorkspaceContext:
        workspace = SimpleNamespace(id="ws-1")
        role = SimpleNamespace(name=role_name)
        membership = SimpleNamespace(role=role)
        return WorkspaceContext(workspace=workspace, membership=membership)

    def test_owner_passes_write_gate(self) -> None:
        dep = require_roles("owner", "admin", "member")
        out = dep(self._ctx("owner"))
        self.assertEqual(out.membership.role.name, "owner")

    def test_viewer_blocked_from_write_gate(self) -> None:
        dep = require_roles("owner", "admin", "member")
        with self.assertRaises(HTTPException) as err:
            dep(self._ctx("viewer"))
        self.assertEqual(err.exception.status_code, 403)

    def test_viewer_allowed_for_read_gate(self) -> None:
        dep = require_roles("owner", "admin", "member", "viewer")
        out = dep(self._ctx("viewer"))
        self.assertEqual(out.membership.role.name, "viewer")

    def test_production_requires_x_workspace_id_header(self) -> None:
        with patch("app.api.deps.settings") as mock_settings:
            mock_settings.environment = "production"
            mock_settings.require_workspace_header_in_production = True
            with self.assertRaises(HTTPException) as err:
                get_workspace_context(MagicMock(), MagicMock(), MagicMock(), None)  # type: ignore[arg-type]
            self.assertEqual(err.exception.status_code, 400)
            self.assertIn("Workspace", err.exception.detail or "")


if __name__ == "__main__":
    unittest.main()
