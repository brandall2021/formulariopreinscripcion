import pytest
from sqlalchemy.orm import Session
from app.alumnos.models import Alumno
from app.auditorias.models import Observacion
from app.auditorias.service import registrar_auditoria
from app.auth.models import Usuario
from app.catalogos.models import Carrera, Convocatoria, TipoDocumento
from app.documentos.models import Documento
from app.solicitudes.models import Solicitud

@pytest.fixture
def solicitud_en_auditoria(db: Session):
    conv = Convocatoria(nombre="2026-aud", anio=2026, activa=True)
    car = Carrera(nombre="Economía", codigo="ECOA", activa=True)
    alumno = Alumno(apellido="López", nombres="María", dni="32123456",
                    email="maria-aud@example.com", celular="+5493815555555")
    td = TipoDocumento(codigo="dni", nombre="DNI")
    auditor = Usuario(email="auditor-aud@example.com", password_hash="x",
                      rol="auditor", activo=True)
    db.add_all([conv, car, alumno, td, auditor])
    db.flush()
    sol = Solicitud(numero="FACE-2026-90002", alumno_id=alumno.id,
                    convocatoria_id=conv.id, carrera_id=car.id,
                    tipo_ingresante="nuevo", dni=alumno.dni, estado="EN_AUDITORIA")
    db.add(sol)
    db.flush()
    doc = Documento(solicitud_id=sol.id, tipo_documento_id=td.id, estado="EN_REVISION")
    db.add(doc)
    db.commit()
    return sol, doc, auditor.id


def test_observacion_cambia_estado(solicitud_en_auditoria, db: Session):
    sol, doc, auditor_id = solicitud_en_auditoria
    eventos = []
    registrar_auditoria(db, sol.id, auditor_id,
                        [{"documento_id": doc.id, "resultado": "OBSERVADO",
                          "motivo": "El reverso del DNI es ilegible."}],
                        on_event=lambda evento, datos: eventos.append(evento))
    assert sol.estado == "PENDIENTE_ALUMNO"
    assert db.query(Observacion).filter_by(documento_id=doc.id).count() == 1
    assert eventos == ["OBSERVADA"]


def test_aprobacion_total(solicitud_en_auditoria, db: Session):
    sol, doc, auditor_id = solicitud_en_auditoria
    eventos = []
    registrar_auditoria(db, sol.id, auditor_id,
                        [{"documento_id": doc.id, "resultado": "APROBADO"}],
                        on_event=lambda evento, datos: eventos.append(evento))
    assert sol.estado == "DOCUMENTACION_APROBADA"
    assert db.get(Documento, doc.id).estado == "APROBADO"
    assert eventos == ["DOCUMENTACION_APROBADA"]
