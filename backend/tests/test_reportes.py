from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
import jwt
from app.alumnos.models import Alumno
from app.catalogos.models import Carrera, Convocatoria
from app.infra.config import get_settings
from app.infra.db import get_db
from app.reportes.router import admin_router, router
from app.solicitudes.models import Solicitud


def _admin_headers():
    token = jwt.encode({"sub": "admin@face.unt.edu.ar", "rol": "admin"},
                       get_settings().secret_key, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}

def test_resumen(db: Session):
    conv = Convocatoria(nombre="2026-rep", anio=2026, activa=True)
    car = Carrera(nombre="Economía", codigo="ECOREP", activa=True)
    alumno = Alumno(apellido="Pérez", nombres="Ana", dni="30123456",
                    email="ana-rep@example.com", celular="+5493815555555")
    db.add_all([conv, car, alumno])
    db.flush()
    db.add(Solicitud(numero="FACE-2026-90005", alumno_id=alumno.id,
                     convocatoria_id=conv.id, carrera_id=car.id,
                     tipo_ingresante="nuevo", dni=alumno.dni, estado="EN_AUDITORIA"))
    db.commit()
    app = FastAPI()
    app.include_router(router)
    app.include_router(admin_router)
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)
    data = client.get("/reportes/resumen", headers=_admin_headers()).json()
    assert data["por_estado"]["EN_AUDITORIA"] == 1
    assert data["total"] >= 1


def test_cierre_administrativo(db: Session):
    conv = Convocatoria(nombre="2026-cierre", anio=2026, activa=True)
    car = Carrera(nombre="Economía", codigo="ECOCI", activa=True)
    alumno = Alumno(apellido="López", nombres="Luis", dni="32123456",
                    email="luis-rep@example.com", celular="+5493815555555")
    db.add_all([conv, car, alumno])
    db.flush()
    sol = Solicitud(numero="FACE-2026-90006", alumno_id=alumno.id,
                    convocatoria_id=conv.id, carrera_id=car.id,
                    tipo_ingresante="nuevo", dni=alumno.dni,
                    estado="DOCUMENTACION_APROBADA")
    db.add(sol)
    db.commit()
    app = FastAPI()
    app.include_router(router)
    app.include_router(admin_router)
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)
    respuesta = client.post(f"/admin/solicitudes/{sol.id}/finalizar",
                            json={"actor": "admin"}, headers=_admin_headers())
    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "FINALIZADA"


def test_rechazo_valida_motivo_y_estado_terminal(db: Session):
    conv = Convocatoria(nombre="2026-rechazo", anio=2026, activa=True)
    car = Carrera(nombre="Economía", codigo="ECORCH", activa=True)
    alumno = Alumno(apellido="López", nombres="Luis", dni="33123456",
                    email="luis-rechazo@example.com", celular="+5493815555555")
    db.add_all([conv, car, alumno])
    db.flush()
    sol = Solicitud(numero="FACE-2026-90007", alumno_id=alumno.id,
                    convocatoria_id=conv.id, carrera_id=car.id,
                    tipo_ingresante="nuevo", dni=alumno.dni, estado="RECIBIDA")
    db.add(sol)
    db.commit()
    app = FastAPI()
    app.include_router(admin_router)
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)
    url = f"/admin/solicitudes/{sol.id}/rechazar"
    assert client.post(url, json={"actor": "admin"}, headers=_admin_headers()).status_code == 422
    respuesta = client.post(url, json={"actor": "admin",
                                       "motivo": "Documentación incompleta"}, headers=_admin_headers())
    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "RECHAZADA"
    # Un segundo rechazo sobre el estado terminal debe ser 409, no 500.
    segundo = client.post(url, json={"actor": "admin", "motivo": "reintento"}, headers=_admin_headers())
    assert segundo.status_code == 409
