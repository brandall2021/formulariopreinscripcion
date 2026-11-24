import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.alumnos.models import Alumno
from app.catalogos.models import Carrera, Convocatoria, TipoDocumento
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
