import unittest
from unittest.mock import MagicMock, patch

from app.core import client_ip as client_ip_mod


class ClientIpTests(unittest.TestCase):
    def test_spoofed_xff_ignored_without_trusted_proxy(self) -> None:
        req = MagicMock()
        req.client = MagicMock()
        req.client.host = "198.51.100.9"
        req.headers = {"x-forwarded-for": "1.2.3.4"}
        with patch.object(client_ip_mod.settings, "use_forwarded_headers", True), patch.object(
            client_ip_mod.settings, "trusted_proxy_ips", "10.0.0.1"
        ):
            ip = client_ip_mod.get_client_ip(req)
            self.assertEqual(ip, "198.51.100.9")

    def test_xff_used_when_peer_is_trusted_proxy(self) -> None:
        req = MagicMock()
        req.client = MagicMock()
        req.client.host = "127.0.0.1"
        req.headers = {"x-forwarded-for": "203.0.113.5, 10.0.0.2"}
        with patch.object(client_ip_mod.settings, "use_forwarded_headers", True), patch.object(
            client_ip_mod.settings, "trusted_proxy_ips", "127.0.0.1,::1"
        ):
            ip = client_ip_mod.get_client_ip(req)
            self.assertEqual(ip, "203.0.113.5")


if __name__ == "__main__":
    unittest.main()
