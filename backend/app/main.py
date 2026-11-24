from app import alumnos, auditorias, auth, catalogos, documentos, notificaciones, solicitudes  # noqa: F401
from fastapi import FastAPI
app = FastAPI(title="FACE Preinscripción API")

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
