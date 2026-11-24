from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.catalogos.models import Carrera, Convocatoria
from app.catalogos.router import router
from app.catalogos.seed import seed_catalogos
from app.infra.db import get_db

def test_seed_y_endpoints(db: Session):
    seed_catalogos(db)
    seed_catalogos(db)  # idempotente
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)
    carreras = client.get("/catalogos/carreras").json()
    tipos = client.get("/catalogos/tipos-documentos").json()
    assert [c["nombre"] for c in carreras] == ["Contador Público", "Economía", "Administración"]
    assert {t["codigo"] for t in tipos} == {
        "dni", "foto_carnet", "acta_nacimiento", "titulo_secundario",
        "formulario_siu", "comprobante_pago",
    }
    conv = db.query(Convocatoria).filter_by(nombre="Convocatoria 2026").one()
    car = db.query(Carrera).filter_by(codigo="CP").one()
    requisitos = client.get("/catalogos/requisitos",
                            params={"convocatoria_id": conv.id, "carrera_id": car.id,
                                    "tipo_ingresante": "nuevo"}).json()
    assert len(requisitos) == 6


def test_seed_con_otra_convocatoria(db: Session):
    db.add(Convocatoria(nombre="Convocatoria 2025", anio=2025, activa=False))
    db.commit()
    seed_catalogos(db)
    assert db.query(Carrera).filter_by(codigo="CP").one() is not None
    assert db.query(Convocatoria).filter_by(nombre="Convocatoria 2026").one() is not None
