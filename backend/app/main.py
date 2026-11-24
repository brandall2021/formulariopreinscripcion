from app import alumnos, auditorias, auth, catalogos, consentimientos, documentos, historial, notificaciones, solicitudes  # noqa: F401
from app.auth.router import router as auth_router
from app.catalogos.router import router as catalogos_router
from app.catalogos.seed import seed_catalogos
from app.infra.db import SessionLocal
from fastapi import FastAPI
app = FastAPI(title="FACE Preinscripción API")
app.include_router(auth_router)
app.include_router(catalogos_router)

@app.on_event("startup")
def startup_seed():
    with SessionLocal() as db:
        seed_catalogos(db)

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
