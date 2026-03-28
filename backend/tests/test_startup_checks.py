import unittest

from app.core.config import Settings
from app.core.startup_checks import validate_production_settings


class StartupChecksTests(unittest.TestCase):
    def test_production_rejects_postgres_postgres_credentials(self) -> None:
        s = Settings(
            environment="production",
            secret_key="not-the-default-dev-secret-change-me-xxxxxxxx",
            database_url="postgresql+psycopg://postgres:postgres@db.example.com:5432/app",
            redis_url="redis://:somesecret@redis.example.com:6379/0",
            ingestion_async_enabled=True,
        )
        with self.assertRaises(RuntimeError) as ctx:
            validate_production_settings(s)
        self.assertIn("postgres:postgres", str(ctx.exception).lower())

    def test_production_rejects_localhost_database_host(self) -> None:
        s = Settings(
            environment="production",
            secret_key="not-the-default-dev-secret-change-me-xxxxxxxx",
            database_url="postgresql+psycopg://u:p@localhost:5432/app",
            redis_url="redis://:somesecret@redis.example.com:6379/0",
            ingestion_async_enabled=True,
        )
        with self.assertRaises(RuntimeError) as ctx:
            validate_production_settings(s)
        self.assertIn("localhost", str(ctx.exception).lower())

    def test_production_requires_trusted_proxy_when_forwarded_headers(self) -> None:
        s = Settings(
            environment="production",
            secret_key="not-the-default-dev-secret-change-me-xxxxxxxx",
            database_url="postgresql+psycopg://u:p@db.example.com:5432/app",
            redis_url="redis://:somesecret@redis.example.com:6379/0",
            use_forwarded_headers=True,
            trusted_proxy_ips=" ",
            ingestion_async_enabled=True,
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

    def test_production_rejects_empty_secret(self) -> None:
        s = Settings(
            environment="production",
            secret_key="   ",
            database_url="postgresql+psycopg://u:p@db.example.com:5432/app?sslmode=require",
            redis_url="redis://:somesecret@redis.example.com:6379/0",
            ingestion_async_enabled=True,
        )
        with self.assertRaises(RuntimeError) as ctx:
            validate_production_settings(s)
        self.assertIn("empty", str(ctx.exception).lower())

    def test_production_rejects_short_secret(self) -> None:
        s = Settings(
            environment="production",
            secret_key="x" * 20,
            database_url="postgresql+psycopg://u:p@db.example.com:5432/app?sslmode=require",
            redis_url="redis://:somesecret@redis.example.com:6379/0",
            secret_key_min_length=32,
            ingestion_async_enabled=True,
        )
        with self.assertRaises(RuntimeError) as ctx:
            validate_production_settings(s)
        self.assertIn("32", str(ctx.exception))

    def test_production_requires_async_ingestion(self) -> None:
        s = Settings(
            environment="production",
            secret_key="not-the-default-dev-secret-change-me-xxxxxxxx",
            database_url="postgresql+psycopg://u:p@db.example.com:5432/app?sslmode=require",
            redis_url="redis://:somesecret@redis.example.com:6379/0",
            ingestion_async_enabled=False,
        )
        with self.assertRaises(RuntimeError) as ctx:
            validate_production_settings(s)
        self.assertIn("INGESTION_ASYNC", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
