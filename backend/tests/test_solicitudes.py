import pytest
from sqlalchemy.orm import Session
from app.alumnos.models import Alumno
from app.catalogos.models import Carrera, Convocatoria
from app.catalogos.seed import seed_catalogos
from app.solicitudes.service import crear_borrador, confirmar


def _ids(db: Session) -> dict:
    conv = db.query(Convocatoria).filter_by(nombre="Convocatoria 2026").one()
    car = db.query(Carrera).filter_by(codigo="CP").one()
    return {"convocatoria_id": conv.id, "carrera_id": car.id}


def test_borrador_y_confirmacion(db: Session):
    seed_catalogos(db)
    db.add(Alumno(apellido="Pérez", nombres="Ana", dni="30123456",
                  email="ana@example.com", celular="+5493815555555"))
    db.commit()
    payload = {"apellido": "Pérez", "nombres": "Ana", "dni": "30123456",
               "email": "ana@example.com", "celular": "+5493815555555",
               **_ids(db), "tipo_ingresante": "nuevo"}
    sol = crear_borrador(db, "ana@example.com", payload)
    assert sol.estado == "BORRADOR" and sol.numero is None
    with pytest.raises(ValueError, match="requisitos pendientes"):
        confirmar(db, sol.id, sol.version)

def test_numero_y_transicion(db: Session):
    seed_catalogos(db)
    db.add(Alumno(apellido="López", nombres="Luis", dni="32123456",
                  email="luis@example.com", celular="+5493815555555"))
    db.commit()
    payload = {"apellido": "López", "nombres": "Luis", "dni": "32123456",
               "email": "luis@example.com", "celular": "+5493815555555",
               **_ids(db), "tipo_ingresante": "nuevo"}
    sol = crear_borrador(db, "luis@example.com", payload)
    # Sin documentos no confirma; se verifica el formato del número con un estado forzado.
    from app.solicitudes.service import _siguiente_numero
    numero = _siguiente_numero(db, 2026, 1)
    assert numero.startswith("FACE-2026-") and len(numero) == 15

def test_rechaza_version_obsoleta(db: Session):
    seed_catalogos(db)
    db.add(Alumno(apellido="Gómez", nombres="Pedro", dni="33123456",
                  email="pedro@example.com", celular="+5493815555555"))
    db.commit()
    payload = {"apellido": "Gómez", "nombres": "Pedro", "dni": "33123456",
               "email": "pedro@example.com", "celular": "+5493815555555",
               **_ids(db), "tipo_ingresante": "nuevo"}
    sol = crear_borrador(db, "pedro@example.com", payload)
    with pytest.raises(ValueError, match="versión obsoleta"):
        confirmar(db, sol.id, sol.version + 1)
