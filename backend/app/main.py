from app import alumnos, auditorias, auth, catalogos, consentimientos, documentos, historial, notificaciones, solicitudes  # noqa: F401
from app.auth.router import router as auth_router
from fastapi import FastAPI
app = FastAPI(title="FACE Preinscripción API")
app.include_router(auth_router)

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
