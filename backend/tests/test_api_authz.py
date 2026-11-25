import time

import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.alumnos.models import Alumno
from app.auditorias.models import Auditoria
from app.auth.models import Usuario
from app.catalogos.models import Carrera, Convocatoria, TipoDocumento
from app.documentos.models import Documento, DocumentoVersion
from app.documentos.router import get_store
from app.infra.config import get_settings
from app.infra.db import get_db
from app.main import app
from app.solicitudes.models import Solicitud


class FakeStore:
    """No debe usarse: los tests solo ejercitan autorización."""


def _token(email: str, rol: str | None = "auditor") -> str:
    payload = {"sub": email, "exp": int(time.time()) + 3600}
    if rol is not None:
        payload["rol"] = rol
    return jwt.encode(payload, get_settings().secret_key, algorithm="HS256")


@pytest.fixture
async def client(db, monkeypatch):
    async def _get_db():
        yield db

    class NoopTask:
        def delay(self, *args, **kwargs):
            return None

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_store] = lambda: FakeStore()
    monkeypatch.setattr("app.auditorias.router.enviar_notificacion", NoopTask())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def escenario(db):
    conv = Convocatoria(nombre="2026-authz", anio=2026, activa=True)
    car = Carrera(nombre="Contador Público", codigo="CPA", activa=True)
    alumno = Alumno(apellido="Test", nombres="Authz", dni="30111222",
                    email="alumno-authz@example.com", celular="+5491100000000")
    td = TipoDocumento(codigo="dni", nombre="DNI")
    autenticado = Usuario(email="auditor-authz@example.com", password_hash="x",
                          rol="auditor", activo=True)
    otro = Usuario(email="auditor-otro@example.com", password_hash="x",
                   rol="auditor", activo=True)
    db.add_all([conv, car, alumno, td, autenticado, otro])
    db.flush()
    sol = Solicitud(numero="FACE-2026-99001", alumno_id=alumno.id,
                    convocatoria_id=conv.id, carrera_id=car.id,
                    tipo_ingresante="nuevo", dni=alumno.dni,
                    estado="EN_AUDITORIA")
    db.add(sol)
    db.flush()
    doc = Documento(solicitud_id=sol.id, tipo_documento_id=td.id,
                    estado="EN_REVISION", version=1)
    db.add(doc)
    db.flush()
    version = DocumentoVersion(documento_id=doc.id, numero=1,
                               object_key="test/dni/v1.pdf",
                               mime="application/pdf", bytes=1,
                               checksum="x", creado_por="test")
    db.add(version)
    db.flush()
    doc.version_vigente_id = version.id
    db.commit()
    return sol, doc, version, autenticado, otro


@pytest.mark.asyncio
async def test_auditoria_ignora_auditor_id_del_cliente(client, db, escenario):
    sol, doc, _version, autenticado, otro = escenario
    resp = await client.post(
        f"/auditorias/solicitudes/{sol.id}",
        json={
            "auditor_id": otro.id,
            "decisiones": [{"documento_id": doc.id, "version": doc.version,
                            "resultado": "APROBADO"}],
        },
        headers={"Authorization": f"Bearer {_token(autenticado.email)}"},
    )
    assert resp.status_code == 200, resp.text
    audit = db.query(Auditoria).one()
    assert audit.auditor_id == autenticado.id


@pytest.mark.asyncio
async def test_auditoria_sin_token_rechazada(client, escenario):
    sol, doc, _version, _autenticado, _otro = escenario
    resp = await client.post(
        f"/auditorias/solicitudes/{sol.id}",
        json={"decisiones": [{"documento_id": doc.id, "version": doc.version,
                              "resultado": "APROBADO"}]},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_auditoria_con_rol_alumno_rechazada(client, escenario):
    sol, doc, _version, _autenticado, _otro = escenario
    token = jwt.encode(
        {"sub": "alumno@example.com", "exp": int(time.time()) + 3600},
        get_settings().secret_key, algorithm="HS256")
    resp = await client.post(
        f"/auditorias/solicitudes/{sol.id}",
        json={"decisiones": [{"documento_id": doc.id, "version": doc.version,
                              "resultado": "APROBADO"}]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_validar_documento_requiere_autenticacion(client, escenario):
    _sol, _doc, version, _autenticado, _otro = escenario
    resp = await client.post(f"/documentos/{version.id}/validar")
    assert resp.status_code == 401
