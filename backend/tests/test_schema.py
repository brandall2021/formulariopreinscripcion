import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.alumnos.models import Alumno
from app.auth.models import Usuario
from app.catalogos.models import Carrera, Convocatoria, TipoDocumento
from app.auditorias.models import Auditoria, Observacion
from app.consentimientos.models import Consentimiento
from app.documentos.models import Documento, DocumentoVersion
from app.historial.models import HistorialEstado
from app.notificaciones.models import Notificacion
from app.solicitudes.models import Solicitud
from app.solicitudes.state import InvalidTransition, transition


def test_dni_unico_por_convocatoria(db: Session):
    conv = Convocatoria(nombre="2026", anio=2026, activa=True)
    carrera = Carrera(nombre="Economía", codigo="ECO", activa=True)
    alumno = Alumno(apellido="Pérez", nombres="Juan", dni="30123456",
                    email="juan@example.com", celular="+5493815555555")
    db.add_all([conv, carrera, alumno])
    db.flush()
    db.add(Solicitud(numero="FACE-2026-00001", alumno_id=alumno.id,
                     convocatoria_id=conv.id, carrera_id=carrera.id,
                     tipo_ingresante="nuevo", dni=alumno.dni, estado="BORRADOR"))
    db.flush()
    db.add(Solicitud(numero="FACE-2026-00002", alumno_id=alumno.id,
                     convocatoria_id=conv.id, carrera_id=carrera.id,
                     tipo_ingresante="nuevo", dni=alumno.dni, estado="BORRADOR"))
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_transiciones_validas():
    assert transition("RECIBIDA", "EN_VALIDACION") == "EN_VALIDACION"
    with pytest.raises(InvalidTransition):
        transition("BORRADOR", "DOCUMENTACION_APROBADA")


def test_rechazo_desde_estados_activos():
    activos = ["BORRADOR", "RECIBIDA", "EN_VALIDACION", "EN_AUDITORIA",
               "OBSERVADA", "PENDIENTE_ALUMNO", "REENVIADA", "EN_REAUDITORIA",
               "DOCUMENTACION_APROBADA"]
    for estado in activos:
        assert transition(estado, "RECHAZADA") == "RECHAZADA"
    with pytest.raises(InvalidTransition):
        transition("FINALIZADA", "RECHAZADA")
    with pytest.raises(InvalidTransition):
        transition("RECHAZADA", "RECIBIDA")


def test_versiones_y_observaciones(db: Session):
    conv = Convocatoria(nombre="2026", anio=2026, activa=True)
    carrera = Carrera(nombre="Economía", codigo="ECO2", activa=True)
    alumno = Alumno(apellido="López", nombres="María", dni="32123456",
                    email="maria@example.com", celular="+5493815555556")
    td = TipoDocumento(codigo="dni", nombre="DNI")
    db.add_all([conv, carrera, alumno, td])
    db.flush()
    sol = Solicitud(numero="FACE-2026-00003", alumno_id=alumno.id,
                    convocatoria_id=conv.id, carrera_id=carrera.id,
                    tipo_ingresante="nuevo", dni=alumno.dni, estado="BORRADOR")
    db.add(sol)
    db.flush()
    doc = Documento(solicitud_id=sol.id, tipo_documento_id=td.id, estado="PENDIENTE")
    db.add(doc)
    db.flush()
    db.add_all([
        DocumentoVersion(documento_id=doc.id, numero=1,
                         object_key="solicitudes/3/dni/v1.pdf", mime="application/pdf",
                         bytes=1024, checksum="abc", creado_por="alumno@example.com"),
        DocumentoVersion(documento_id=doc.id, numero=1,
                         object_key="solicitudes/3/dni/v1b.pdf", mime="application/pdf",
                         bytes=1024, checksum="def", creado_por="alumno@example.com"),
    ])
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_idempotency_notificaciones(db: Session):
    conv = Convocatoria(nombre="2026b", anio=2026, activa=True)
    carrera = Carrera(nombre="Administración", codigo="ADM", activa=True)
    alumno = Alumno(apellido="Gómez", nombres="Pedro", dni="33123456",
                    email="pedro@example.com", celular="+5493815555557")
    db.add_all([conv, carrera, alumno])
    db.flush()
    sol = Solicitud(numero="FACE-2026-00004", alumno_id=alumno.id,
                    convocatoria_id=conv.id, carrera_id=carrera.id,
                    tipo_ingresante="nuevo", dni=alumno.dni, estado="BORRADOR")
    db.add(sol)
    db.flush()
    key = "obs|email|1|dni"
    db.add(Notificacion(solicitud_id=sol.id, evento="OBSERVADA", canal="email",
                        destinatario="pedro@example.com", estado="PENDIENTE",
                        asunto="Observaciones", cuerpo="Revisar DNI",
                        idempotency_key=key))
    db.add(Notificacion(solicitud_id=sol.id, evento="OBSERVADA", canal="email",
                        destinatario="pedro@example.com", estado="PENDIENTE",
                        asunto="Observaciones", cuerpo="Revisar DNI",
                        idempotency_key=key))
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_modelos_secundarios_y_caso_feliz(db: Session):
    conv = Convocatoria(nombre="2026-caso", anio=2026, activa=True)
    carrera = Carrera(nombre="Administración", codigo="CASO", activa=True)
    alumno = Alumno(apellido="Díaz", nombres="Luis", dni="35123456",
                    email="caso@example.com", celular="+5493815555558")
    td = TipoDocumento(codigo="dni-caso", nombre="DNI")
    auditor = Usuario(email="auditor-caso@example.com", password_hash="x",
                      rol="auditor", activo=True)
    db.add_all([conv, carrera, alumno, td, auditor])
    db.flush()
    sol = Solicitud(numero="FACE-2026-00005", alumno_id=alumno.id,
                    convocatoria_id=conv.id, carrera_id=carrera.id,
                    tipo_ingresante="nuevo", dni=alumno.dni, estado="BORRADOR")
    db.add(sol)
    db.flush()
    doc = Documento(solicitud_id=sol.id, tipo_documento_id=td.id, estado="PENDIENTE")
    db.add(doc)
    db.flush()
    db.add_all([
        DocumentoVersion(documento_id=doc.id, numero=1, object_key="s/1/dni/v1.pdf",
                         mime="application/pdf", bytes=10, checksum="a",
                         creado_por="alumno@example.com"),
        DocumentoVersion(documento_id=doc.id, numero=2, object_key="s/1/dni/v2.pdf",
                         mime="application/pdf", bytes=10, checksum="b",
                         creado_por="alumno@example.com"),
    ])
    audit = Auditoria(solicitud_id=sol.id, auditor_id=auditor.id,
                      resultado="OBSERVADO")
    db.add(audit)
    db.flush()
    db.add_all([
        Observacion(auditoria_id=audit.id, documento_id=doc.id, motivo="Ilegible"),
        HistorialEstado(solicitud_id=sol.id, estado_anterior="BORRADOR",
                        estado_nuevo="RECIBIDA", actor="alumno"),
        Consentimiento(alumno_id=alumno.id, canal="whatsapp", aceptado=True),
        Notificacion(solicitud_id=sol.id, evento="OBSERVADA", canal="email",
                     destinatario="caso@example.com", estado="PENDIENTE",
                     asunto="Observaciones", cuerpo="Revisar DNI",
                     idempotency_key="otra|email|1|dni"),
    ])
    db.commit()
    assert db.query(DocumentoVersion).filter_by(documento_id=doc.id).count() == 2
    assert db.query(Observacion).filter_by(auditoria_id=audit.id).count() == 1
    assert db.query(HistorialEstado).filter_by(solicitud_id=sol.id).count() == 1
    assert db.query(Consentimiento).filter_by(alumno_id=alumno.id).count() == 1
