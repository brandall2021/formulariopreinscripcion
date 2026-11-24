from app import alumnos, auditorias, auth, catalogos, consentimientos, documentos, historial, notificaciones, solicitudes  # noqa: F401
from app.auditorias.router import router as auditorias_router
from app.auth.router import router as auth_router
from app.catalogos.router import router as catalogos_router
from app.catalogos.seed import seed_catalogos, seed_usuarios
from app.documentos.router import router as documentos_router
from app.infra.db import SessionLocal
from app.notificaciones.router import router as consentimientos_router
from app.reportes.router import router as reportes_router, admin_router
from app.solicitudes.router import router as solicitudes_router
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
app = FastAPI(title="FACE Preinscripción API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router)
app.include_router(catalogos_router)
app.include_router(documentos_router)
app.include_router(solicitudes_router)
app.include_router(auditorias_router)
app.include_router(consentimientos_router)
app.include_router(reportes_router)
app.include_router(admin_router)

@app.on_event("startup")
def startup_seed():
    with SessionLocal() as db:
        seed_usuarios(db)
        seed_catalogos(db)

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
