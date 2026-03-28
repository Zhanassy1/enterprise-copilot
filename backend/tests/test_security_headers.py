import unittest

from fastapi.testclient import TestClient

from app.main import app


class SecurityHeadersTests(unittest.TestCase):
    def test_healthz_has_security_headers(self) -> None:
        client = TestClient(app)
        r = client.get("/healthz")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(r.headers.get("X-Frame-Options"), "DENY")
        self.assertIn("Referrer-Policy", r.headers)


if __name__ == "__main__":
    unittest.main()
