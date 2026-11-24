import pytest
from httpx import ASGITransport, AsyncClient

from app.infra.config import get_settings
from app.main import app


def test_settings_locales(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://face:face@localhost:5432/face")
    s = get_settings()
    assert s.database_url.endswith("/face")
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
