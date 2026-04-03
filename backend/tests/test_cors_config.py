import unittest

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from app.bootstrap.startup import configure_cors
from app.core.config import Settings


def _cors_middleware_options(app: FastAPI) -> dict:
    for m in app.user_middleware:
        if m.cls is CORSMiddleware:
            return dict(m.kwargs)
    raise AssertionError("CORSMiddleware not registered")


class CorsConfigTests(unittest.TestCase):
    def test_production_has_no_allow_origin_regex(self) -> None:
        app = FastAPI()
        configure_cors(
            app,
            Settings(environment="production", cors_origins="https://app.example.com"),
        )
        opts = _cors_middleware_options(app)
        self.assertNotIn("allow_origin_regex", opts)

    def test_local_includes_allow_origin_regex(self) -> None:
        app = FastAPI()
        configure_cors(
            app,
            Settings(environment="local", cors_origins="http://localhost:5173"),
        )
        opts = _cors_middleware_options(app)
        rgx = opts.get("allow_origin_regex")
        self.assertIsInstance(rgx, str)
        self.assertIn(r"192\.168", rgx)


if __name__ == "__main__":
    unittest.main()
