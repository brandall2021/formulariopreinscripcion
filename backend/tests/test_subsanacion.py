import hashlib
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
import jwt
from app.infra.config import get_settings
from app.alumnos.models import Alumno
from app.auditorias.models import Auditoria, Observacion
from app.auth.models import Usuario
from app.catalogos.models import Carrera, Convocatoria, TipoDocumento
from app.documentos.models import Documento, DocumentoVersion
from app.documentos.service import registrar_documento
from app.infra.db import get_db
from app.solicitudes.models import Solicitud
from app.solicitudes.router import router as solicitudes_router
from app.solicitudes.service import registrar_transicion
import worker.tasks as tasks

class FakeStore:
    def put_bytes(self, key, data): pass
    def get_bytes(self, key): return b""
    def exists(self, key): return True
    def presigned_put(self, key, ct, expires): return f"http://minio/{key}"
    def presigned_get(self, key, expires): return f"http://minio/{key}"

def test_reemplazo_conserva_versiones(db: Session):
    conv = Convocatoria(nombre="2026-sub", anio=2026, activa=True)
    car = Carrera(nombre="Economía", codigo="ECOSUB", activa=True)
    alumno = Alumno(apellido="Gómez", nombres="Pedro", dni="33123456",
                    email="pedro-sub@example.com", celular="+5493815555555")
    td = TipoDocumento(codigo="dni", nombre="DNI", tamano_maximo_bytes=10485760)
    auditor = Usuario(email="auditor-sub@example.com", password_hash="x",
                      rol="auditor", activo=True)
    db.add_all([conv, car, alumno, td, auditor])
    db.flush()
    sol = Solicitud(numero="FACE-2026-90003", alumno_id=alumno.id,
                    convocatoria_id=conv.id, carrera_id=car.id,
                    tipo_ingresante="nuevo", dni=alumno.dni, estado="PENDIENTE_ALUMNO")
    db.add(sol)
    db.flush()
    doc = Documento(solicitud_id=sol.id, tipo_documento_id=td.id, estado="OBSERVADO")
    db.add(doc)
    db.flush()
    db.add(DocumentoVersion(documento_id=doc.id, numero=1, object_key="s/1/dni/v1.pdf",
                            mime="application/pdf", bytes=3, checksum="old",
                            creado_por="alumno"))
    audit = Auditoria(solicitud_id=sol.id, auditor_id=auditor.id, resultado="OBSERVADO")
    db.add(audit)
    db.flush()
    db.add(Observacion(auditoria_id=audit.id, documento_id=doc.id,
                       motivo="Imagen ilegible"))
    db.commit()

    data = b"new"
    registrar_documento(db, sol.id, td.id, "dni.pdf", "application/pdf", len(data),
                        hashlib.sha256(data).hexdigest(), "pedro-sub@example.com",
                        FakeStore())

    app = FastAPI()
    app.include_router(solicitudes_router)
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)
    token = jwt.encode({"sub": "pedro-sub@example.com", "exp": 9999999999}, get_settings().secret_key, algorithm="HS256")
    observados = client.get(f"/solicitudes/{sol.id}/documentos-observados", headers={"Authorization": f"Bearer {token}"}).json()
    assert observados[0]["motivo"] == "Imagen ilegible"

    llamados = []
    original_validar = tasks.validar_documentos_solicitud.delay
    original_notificar = tasks.enviar_notificacion.delay
    tasks.validar_documentos_solicitud.delay = lambda sid: llamados.append(("validar", sid))
    tasks.enviar_notificacion.delay = lambda nid: llamados.append(("notificar", nid))
    try:
        respuesta = client.post(f"/solicitudes/{sol.id}/reenviar",
                                json={"version": sol.version}, headers={"Authorization": f"Bearer {token}"})
        assert respuesta.status_code == 200
    finally:
        tasks.validar_documentos_solicitud.delay = original_validar
        tasks.enviar_notificacion.delay = original_notificar

    registrar_transicion(db, sol, "EN_REAUDITORIA", "worker")
    assert db.query(DocumentoVersion).filter_by(documento_id=doc.id).count() == 2
    assert db.get(Documento, doc.id).estado == "REEMPLAZADO"
    assert sol.estado == "EN_REAUDITORIA"
    assert ("validar", sol.id) in llamados
    assert any(n[0] == "notificar" for n in llamados)
