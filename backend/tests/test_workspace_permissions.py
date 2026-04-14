import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi import HTTPException

from app.api.deps import (
    ROLE_ORDER,
    WorkspaceContext,
    get_workspace_context,
    require_at_least,
    require_roles,
    role_rank,
)


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

    def test_require_at_least_admin_allows_owner(self) -> None:
        dep = require_at_least("admin")
        out = dep(self._ctx("owner"))
        self.assertEqual(out.membership.role.name, "owner")

    def test_require_at_least_admin_allows_admin(self) -> None:
        dep = require_at_least("admin")
        out = dep(self._ctx("admin"))
        self.assertEqual(out.membership.role.name, "admin")

    def test_require_at_least_admin_blocks_member(self) -> None:
        dep = require_at_least("admin")
        with self.assertRaises(HTTPException) as err:
            dep(self._ctx("member"))
        self.assertEqual(err.exception.status_code, 403)

    def test_require_at_least_member_blocks_viewer(self) -> None:
        dep = require_at_least("member")
        with self.assertRaises(HTTPException) as err:
            dep(self._ctx("viewer"))
        self.assertEqual(err.exception.status_code, 403)

    def test_require_at_least_owner_only(self) -> None:
        dep = require_at_least("owner")
        dep(self._ctx("owner"))
        with self.assertRaises(HTTPException) as err:
            dep(self._ctx("admin"))
        self.assertEqual(err.exception.status_code, 403)

    def test_role_rank_matches_role_order(self) -> None:
        self.assertEqual(role_rank("viewer"), ROLE_ORDER["viewer"])
        self.assertEqual(role_rank("OWNER"), ROLE_ORDER["owner"])
        self.assertIsNone(role_rank("nope"))

    def test_requires_x_workspace_id_header(self) -> None:
        with self.assertRaises(HTTPException) as err:
            get_workspace_context(MagicMock(), MagicMock(), None)  # type: ignore[arg-type]
        self.assertEqual(err.exception.status_code, 400)
        self.assertIn("Workspace", err.exception.detail or "")


if __name__ == "__main__":
    unittest.main()
