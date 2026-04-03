from starlette.routing import Mount
from starlette.testclient import TestClient

from app.core.config import settings
from app.main import create_app


def test_create_app_healthz_and_mount() -> None:
    app = create_app()
    assert app.title == settings.app_name
    client = TestClient(app)
    assert client.get("/healthz").json() == {"ok": True}
    mount_paths = [r.path for r in app.routes if isinstance(r, Mount)]
    assert settings.api_v1_prefix in mount_paths
