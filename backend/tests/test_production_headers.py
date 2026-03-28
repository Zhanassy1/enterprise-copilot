import unittest
from unittest.mock import patch

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


if __name__ == "__main__":
    unittest.main()
