import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
import jwt
from app.infra.config import get_settings
from app.alumnos.models import Alumno
from app.catalogos.models import Carrera, Convocatoria, RequisitoDocumental
from app.catalogos.seed import seed_catalogos
from app.documentos.models import Documento
from app.historial.models import HistorialEstado
from app.infra.db import get_db
from app.solicitudes.router import router as solicitudes_router
from app.solicitudes.service import crear_borrador, confirmar



def _alumno_headers(email="ana@example.com"):
    token = jwt.encode({"sub": email, "exp": 9999999999}, get_settings().secret_key, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}
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


def _borrador_con_requisitos(db: Session, dni: str, email: str):
    seed_catalogos(db)
    db.add(Alumno(apellido="Éxito", nombres="Ana", dni=dni,
                  email=email, celular="+5493815555559"))
    db.commit()
    ids = _ids(db)
    sol = crear_borrador(db, email, {
        "apellido": "Éxito", "nombres": "Ana", "dni": dni, "email": email,
        "celular": "+5493815555559", **ids, "tipo_ingresante": "nuevo"})
    requisitos = db.query(RequisitoDocumental).filter_by(
        convocatoria_id=ids["convocatoria_id"], carrera_id=ids["carrera_id"],
        tipo_ingresante="nuevo").all()
    db.add_all(Documento(solicitud_id=sol.id,
                         tipo_documento_id=r.tipo_documento_id,
                         estado="RECIBIDO") for r in requisitos)
    db.commit()
    return sol


def test_confirmacion_exitosa_genera_numero_e_historial(db: Session):
    sol = _borrador_con_requisitos(db, "36123456", "exito@example.com")
    llamados = []
    confirmada = confirmar(db, sol.id, sol.version, on_confirm=llamados.append)
    assert confirmada.estado == "RECIBIDA"
    assert confirmada.numero.startswith("FACE-2026-") and len(confirmada.numero) == 15
    assert llamados == [sol.id]
    hist = db.query(HistorialEstado).filter_by(solicitud_id=sol.id).one()
    assert hist.estado_anterior == "BORRADOR" and hist.estado_nuevo == "RECIBIDA"


def test_rechaza_confirmacion_duplicada(db: Session):
    sol = _borrador_con_requisitos(db, "37123456", "dup@example.com")
    primera = confirmar(db, sol.id, sol.version)
    with pytest.raises(ValueError, match="solicitud no confirmable"):
        confirmar(db, sol.id, primera.version)
    assert db.query(HistorialEstado).filter_by(solicitud_id=sol.id).count() == 1


def test_endpoint_confirmar_409_y_404(db: Session):
    sol = _borrador_con_requisitos(db, "38123456", "http@example.com")
    app = FastAPI()
    app.include_router(solicitudes_router)
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)
    assert client.get("/solicitudes/999999", headers=_alumno_headers("http@example.com")).status_code == 404
    respuesta = client.post(f"/solicitudes/{sol.id}/confirmar",
                            json={"version": sol.version + 1}, headers=_alumno_headers("http@example.com"))
    assert respuesta.status_code == 409
