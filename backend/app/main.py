import os
import time
from collections import defaultdict, deque

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from app import alumnos, auditorias, auth, catalogos, consentimientos, documentos, historial, notificaciones, solicitudes  # noqa: F401
from app.auditorias.router import router as auditorias_router
from app.auth.router import router as auth_router
from app.catalogos.router import router as catalogos_router
from app.catalogos.seed import seed_catalogos, seed_usuarios
from app.documentos.router import router as documentos_router
from app.infra.config import get_settings
from app.infra.db import SessionLocal
from app.notificaciones.router import router as consentimientos_router
from app.reportes.router import router as reportes_router, admin_router
from app.solicitudes.router import router as solicitudes_router

settings = get_settings()
app = FastAPI(
    title="FACE Preinscripción API",
    docs_url="/docs" if settings.expose_docs else None,
    redoc_url="/redoc" if settings.expose_docs else None,
    openapi_url="/openapi.json" if settings.expose_docs else None,
)
origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:4200").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_RATE_LIMITS = {"/auth/request-otp": (5, 60), "/auth/verify-otp": (10, 60), "/auth/admin/login": (10, 60)}
_rate_hits: dict[str, deque[float]] = defaultdict(deque)


@app.middleware("http")
async def security_and_rate_limit(request: Request, call_next):
    now = time.time()
    path = request.url.path
    limit = _RATE_LIMITS.get(path)
    if limit:
        max_hits, window = limit
        ip = request.client.host if request.client else "unknown"
        key = f"{ip}:{path}"
        hits = _rate_hits[key]
        while hits and now - hits[0] > window:
            hits.popleft()
        if len(hits) >= max_hits:
            return JSONResponse({"detail": "demasiadas solicitudes, intente más tarde"}, status_code=429)
        hits.append(now)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

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
        if settings.seed_demo:
            seed_usuarios(db)
            seed_catalogos(db)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
