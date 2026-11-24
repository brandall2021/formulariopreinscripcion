from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.alumnos.models import Alumno
from app.catalogos.models import Carrera, Convocatoria
from app.infra.db import get_db
from app.reportes.router import admin_router, router
from app.solicitudes.models import Solicitud

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
    data = client.get("/reportes/resumen").json()
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
                            json={"actor": "admin"})
    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "FINALIZADA"
