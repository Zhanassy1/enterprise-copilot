import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from starlette.responses import Response

from app import main


class ProductionHeadersTests(unittest.TestCase):
    def test_security_headers_applied_in_production(self) -> None:
        r = Response()
        with patch.object(main.settings, "environment", "production"):
            main._apply_production_security_headers(r)
        self.assertEqual(r.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(r.headers.get("X-Frame-Options"), "DENY")

    def test_security_headers_skipped_outside_production(self) -> None:
        r = Response()
        with patch.object(main.settings, "environment", "local"):
            main._apply_production_security_headers(r)
        self.assertIsNone(r.headers.get("X-Frame-Options"))

    def test_healthz_middleware_sets_security_headers_in_production(self) -> None:
        from app.main import app

        with patch.object(main.settings, "environment", "production"):
            c = TestClient(app)
            r = c.get("/healthz")
        self.assertEqual(r.headers.get("X-Frame-Options"), "DENY")
        self.assertEqual(r.headers.get("X-Content-Type-Options"), "nosniff")


if __name__ == "__main__":
    unittest.main()
