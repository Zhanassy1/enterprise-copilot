import unittest
from unittest.mock import MagicMock

from app.core.trusted_proxy import get_effective_client_ip


class TrustedProxyTests(unittest.TestCase):
    def test_without_forwarded_returns_direct(self) -> None:
        req = MagicMock()
        req.client.host = "203.0.113.5"
        req.headers = {}
        ip = get_effective_client_ip(req, use_forwarded_headers=False, trusted_proxy_ips="127.0.0.1")
        self.assertEqual(ip, "203.0.113.5")

    def test_untrusted_direct_skips_xff(self) -> None:
        req = MagicMock()
        req.client.host = "198.51.100.2"
        req.headers = {"x-forwarded-for": "203.0.113.10"}
        ip = get_effective_client_ip(req, use_forwarded_headers=True, trusted_proxy_ips="10.0.0.0/8")
        self.assertEqual(ip, "198.51.100.2")

    def test_trusted_proxy_uses_xff_first_hop(self) -> None:
        req = MagicMock()
        req.client.host = "10.0.0.1"
        req.headers = {"x-forwarded-for": "203.0.113.10, 10.0.0.1"}
        ip = get_effective_client_ip(req, use_forwarded_headers=True, trusted_proxy_ips="10.0.0.0/8")
        self.assertEqual(ip, "203.0.113.10")


if __name__ == "__main__":
    unittest.main()
