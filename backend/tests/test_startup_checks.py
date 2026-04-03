import unittest

from app.core.config import Settings
from app.core.startup_checks import validate_production_settings


def _minimal_production_settings(**kwargs: object) -> Settings:
    """Valid production Settings; override fields per test."""
    base: dict[str, object] = {
        "environment": "production",
        "secret_key": "not-the-default-dev-secret-change-me-xxxxxxxx",
        "database_url": "postgresql+psycopg://u:p@db.example.com:5432/app?sslmode=require",
        "redis_url": "redis://:somesecret@redis.example.com:6379/0",
        "ingestion_async_enabled": True,
        "allow_sync_ingestion_for_dev": False,
        "cors_origins": "https://app.example.com",
        "trusted_proxy_ips": "10.0.0.0/8",
        "storage_backend": "s3",
        "s3_bucket": "bucket",
        "s3_access_key_id": "keyid",
        "s3_secret_access_key": "secretkey",
    }
    base.update(kwargs)
    return Settings(**base)


class StartupChecksTests(unittest.TestCase):
    def test_production_rejects_postgres_postgres_credentials(self) -> None:
        s = _minimal_production_settings(
            database_url="postgresql+psycopg://postgres:postgres@db.example.com:5432/app?sslmode=require",
        )
        with self.assertRaises(RuntimeError) as ctx:
            validate_production_settings(s)
        self.assertIn("postgres:postgres", str(ctx.exception).lower())

    def test_production_rejects_localhost_database_host(self) -> None:
        s = _minimal_production_settings(
            database_url="postgresql+psycopg://u:p@localhost:5432/app?sslmode=require",
        )
        with self.assertRaises(RuntimeError) as ctx:
            validate_production_settings(s)
        self.assertIn("localhost", str(ctx.exception).lower())

    def test_production_requires_trusted_proxy_when_forwarded_headers(self) -> None:
        s = _minimal_production_settings(
            production_require_trusted_proxy_ips=False,
            use_forwarded_headers=True,
            trusted_proxy_ips=" ",
        )
        with self.assertRaises(RuntimeError) as ctx:
            validate_production_settings(s)
        self.assertIn("TRUSTED_PROXY_IPS", str(ctx.exception))

    def test_local_skips_production_rules(self) -> None:
        s = Settings(
            environment="local",
            database_url="postgresql+psycopg://postgres:postgres@localhost:5432/app",
            redis_url="redis://localhost:6379/0",
        )
        validate_production_settings(s)

    def test_production_rejects_default_dev_secret_key(self) -> None:
        """startup_checks.validate_production_settings — app/core/startup_checks.py lines 67-68."""
        s = _minimal_production_settings(secret_key="dev-secret-change-me")
        with self.assertRaises(RuntimeError) as ctx:
            validate_production_settings(s)
        self.assertIn("default dev", str(ctx.exception).lower())

    def test_production_rejects_empty_secret(self) -> None:
        s = _minimal_production_settings(secret_key="   ")
        with self.assertRaises(RuntimeError) as ctx:
            validate_production_settings(s)
        self.assertIn("empty", str(ctx.exception).lower())

    def test_production_rejects_short_secret(self) -> None:
        s = _minimal_production_settings(secret_key="x" * 20, secret_key_min_length=32)
        with self.assertRaises(RuntimeError) as ctx:
            validate_production_settings(s)
        self.assertIn("32", str(ctx.exception))

    def test_production_requires_async_ingestion(self) -> None:
        s = _minimal_production_settings(ingestion_async_enabled=False)
        with self.assertRaises(RuntimeError) as ctx:
            validate_production_settings(s)
        self.assertIn("INGESTION_ASYNC", str(ctx.exception))

    def test_production_rejects_email_capture_mode(self) -> None:
        s = _minimal_production_settings(email_capture_mode=True)
        with self.assertRaises(RuntimeError) as ctx:
            validate_production_settings(s)
        self.assertIn("EMAIL_CAPTURE_MODE", str(ctx.exception))

    def test_production_requires_s3_when_default_strict(self) -> None:
        s = _minimal_production_settings(
            storage_backend="local",
            production_require_s3_backend=True,
        )
        with self.assertRaises(RuntimeError) as ctx:
            validate_production_settings(s)
        self.assertIn("s3", str(ctx.exception).lower())

    def test_production_requires_trusted_proxy_ips_when_default_strict(self) -> None:
        s = _minimal_production_settings(trusted_proxy_ips=" ")
        with self.assertRaises(RuntimeError) as ctx:
            validate_production_settings(s)
        self.assertIn("TRUSTED_PROXY_IPS", str(ctx.exception))

    def test_production_requires_explicit_cors_origins(self) -> None:
        s = _minimal_production_settings(cors_origins="  , , ")
        with self.assertRaises(RuntimeError) as ctx:
            validate_production_settings(s)
        self.assertIn("CORS_ORIGINS", str(ctx.exception))

    def test_production_rejects_allow_sync_ingestion_for_dev(self) -> None:
        s = _minimal_production_settings(allow_sync_ingestion_for_dev=True)
        with self.assertRaises(RuntimeError) as ctx:
            validate_production_settings(s)
        self.assertIn("ALLOW_SYNC_INGESTION_FOR_DEV", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
