import pytest
from httpx import ASGITransport, AsyncClient

from app.infra.config import get_settings
from app.main import app


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_settings_locales(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://face:face@localhost:5432/otro_db")
    s = get_settings()
    assert s.database_url == "postgresql+psycopg://face:face@localhost:5432/otro_db"
    assert s.minio_bucket == "face-documentos"
    assert s.otp_ttl_seconds == 600
    assert s.otp_max_intentos == 5


@pytest.mark.asyncio
async def test_health():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_ready_ok(monkeypatch):
    for name in ("_check_db", "_check_redis", "_check_minio"):
        monkeypatch.setattr(f"app.main.{name}", lambda: True)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "checks": {
        "database": True, "redis": True, "minio": True}}


@pytest.mark.asyncio
async def test_ready_degraded(monkeypatch):
    monkeypatch.setattr("app.main._check_db", lambda: True)
    monkeypatch.setattr("app.main._check_redis", lambda: False)
    monkeypatch.setattr("app.main._check_minio", lambda: True)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["status"] == "degraded"
    assert response.json()["checks"]["redis"] is False
