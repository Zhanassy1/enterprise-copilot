import unittest

from app.api.routers import chat, documents, search


class WorkspaceApiContractTests(unittest.TestCase):
    @staticmethod
    def _dep_calls(route) -> list[str]:
        names: list[str] = []
        for dep in route.dependant.dependencies:
            call = getattr(dep, "call", None)
            if call is not None and hasattr(call, "__name__"):
                names.append(call.__name__)
        return names

    def test_documents_router_has_workspace_scoped_handlers(self) -> None:
        route_deps = {route.path: self._dep_calls(route) for route in documents.router.routes}
        upload_path = "/documents/upload"
        self.assertIn(upload_path, route_deps)
        joined = ",".join(route_deps[upload_path])
        self.assertIn("_dep", joined)

    def test_search_router_uses_workspace_dependency(self) -> None:
        route = next(r for r in search.router.routes if r.path == "/search")
        dep_names = self._dep_calls(route)
        self.assertIn("_dep", dep_names)

    def test_chat_router_uses_workspace_dependency(self) -> None:
        route = next(r for r in chat.router.routes if r.path == "/chat/sessions")
        dep_names = self._dep_calls(route)
        self.assertIn("_dep", dep_names)


if __name__ == "__main__":
    unittest.main()
