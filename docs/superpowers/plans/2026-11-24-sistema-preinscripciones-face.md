# Sistema de Preinscripción FACE — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir el circuito completo de preinscripción y auditoría documental FACE con PostgreSQL, MinIO y notificaciones locales.

**Architecture:** Monorepo con una API FastAPI que posee todas las reglas de negocio, un worker Celery que ejecuta validación y notificaciones, un frontend Angular que consume solo HTTP, e infra local Docker Compose. Cada entrega vertical deja el circuito funcionando de punta a punta.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic, Pydantic v2, Celery + Redis, MinIO SDK, smtplib + Mailpit, pytest + httpx, Angular 19 + TypeScript + Karma/Jasmine, Docker Compose.

**Spec:** `docs/superpowers/specs/2026-11-24-sistema-preinscripciones-face-design.md`

## Global Constraints

- PostgreSQL 16; BD principal en puerto 5432 y BD de pruebas en 5433.
- Archivos aceptados: `application/pdf`, `image/jpeg`, `image/png`.
- Tamaño máximo por archivo: `10485760` bytes (10 MB), configurable por `tipos_documentos`.
- Número de solicitud: `FACE-AAAA-NNNNN`, generado atómicamente al confirmar.
- Un DNI no puede tener dos solicitudes en la misma convocatoria: constraint único `(convocatoria_id, dni)` en `solicitudes`.
- MinIO es privado: URLs prefirmadas con vencimiento de 900 s (subida) y 300 s (descarga); nunca URLs públicas.
- OTP por correo, vigente 600 s, máximo 5 intentos.
- Estados de solicitud y documento exactamente los del spec; toda transición escribe `historial_estados`.
- Las notificaciones las envía el worker, nunca el request de auditoría; `idempotency_key` única.
- Sin OCR/IA, sin integración SIU Guaraní, sin WhatsApp real, sin borrado automático de documentos.
- Datos semilla: convocatoria 2026, carreras `Contador Público`, `Economía`, `Administración`; sin importes/fechas de FACET.

## Estructura de archivos

```
infra/docker-compose.yml, infra/.env.example
backend/pyproject.toml, backend/alembic.ini, backend/README.md
backend/app/infra/{config,db,celery_app,storage,email,whatsapp}.py
backend/app/infra/migrations/{env.py,versions/0001_initial.py}
backend/app/auth/{models,schemas,service,router}.py
backend/app/alumnos/{models,schemas,router}.py
backend/app/catalogos/{models,schemas,router,seed.py}.py
backend/app/solicitudes/{models,schemas,state,service,router}.py
backend/app/documentos/{models,schemas,service,router}.py
backend/app/auditorias/{models,schemas,service,router}.py
backend/app/notificaciones/{models,schemas,events,templates,service,router}.py
backend/app/reportes/router.py
backend/app/main.py
backend/tests/{conftest,test_health,test_schema,test_auth,test_catalogos,test_solicitudes,test_documentos,test_auditorias,test_notificaciones}.py
backend/worker/tasks.py
frontend/ (proyecto Angular standalone generado en la tarea 11)
```

---

### Task 1: Scaffolding, infra local y health check

**Files:**
- Create: `infra/docker-compose.yml`, `infra/.env.example`, `backend/pyproject.toml`, `backend/app/__init__.py`, `backend/app/infra/__init__.py`, `backend/app/infra/config.py`, `backend/app/infra/db.py`, `backend/app/main.py`, `backend/tests/conftest.py`, `backend/tests/test_health.py`, `backend/README.md`

**Interfaces:**
- Consumes: nada.
- Produces: `get_settings() -> Settings` (campos `database_url`, `test_database_url`, `minio_endpoint`, `minio_access_key`, `minio_secret_key`, `minio_bucket`, `redis_url`, `smtp_host`, `smtp_port`, `secret_key`, `otp_ttl_seconds`, `otp_max_intentos`), `Base`, `SessionLocal`, `get_db()`, `app` (FastAPI con `GET /health`).

- [ ] **Step 1: Write the failing test**

`backend/tests/test_health.py`:
```python
import pytest
from httpx import ASGITransport, AsyncClient

from app.infra.config import get_settings
from app.main import app


def test_settings_locales(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://face:face@localhost:5432/face")
    s = get_settings()
    assert s.database_url.endswith("/face")
    assert s.minio_bucket == "face-documentos"
    assert s.otp_ttl_seconds == 600
    assert s.otp_max_intentos == 5


@pytest.mark.asyncio
async def test_health():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_health.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'app'`.

- [ ] **Step 3: Write minimal implementation**

`backend/pyproject.toml`:
```toml
[project]
name = "face-preinscripcion"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.115", "uvicorn[standard]>=0.30", "sqlalchemy>=2.0",
  "psycopg[binary]>=3.2", "pydantic>=2.9", "pydantic-settings>=2.5",
  "alembic>=1.13", "minio>=7.2", "celery[redis]>=5.4",
  "python-multipart>=0.0.9", "email-validator>=2.2",
  "passlib[bcrypt]>=1.7", "pyjwt>=2.9",
]
[project.optional-dependencies]
dev = ["pytest>=8.3", "pytest-asyncio>=0.24", "httpx>=0.27"]
[tool.pytest.ini_options]
asyncio_mode = "auto"
pythonpath = ["."]
```

`backend/app/infra/config.py`:
```python
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="../infra/.env", extra="ignore")
    database_url: str = "postgresql+psycopg://face:face@localhost:5432/face"
    test_database_url: str = "postgresql+psycopg://face:face@localhost:5433/face_test"
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "face-documentos"
    redis_url: str = "redis://localhost:6379/0"
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    secret_key: str = "dev-secret-change-me"
    otp_ttl_seconds: int = 600
    otp_max_intentos: int = 5
    upload_url_ttl: int = 900
    download_url_ttl: int = 300


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

`backend/app/infra/db.py`:
```python
from collections.abc import Iterator
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from app.infra.config import get_settings

class Base(DeclarativeBase):
    pass

engine = create_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

`backend/app/main.py`:
```python
from fastapi import FastAPI
app = FastAPI(title="FACE Preinscripción API")

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

`infra/docker-compose.yml` (solo infra; API/worker/frontend se agregan en tareas posteriores):
```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: face
      POSTGRES_PASSWORD: face
      POSTGRES_DB: face
    ports: ["5432:5432"]
    volumes: [pgdata:/var/lib/postgresql/data]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U face -d face"]
      interval: 5s
      retries: 10
  postgres-test:
    image: postgres:16
    environment:
      POSTGRES_USER: face
      POSTGRES_PASSWORD: face
      POSTGRES_DB: face_test
    ports: ["5433:5432"]
    volumes: [pgtestdata:/var/lib/postgresql/data]
  minio:
    image: minio/minio:RELEASE.2024-11-07T00-52-20Z
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    ports: ["9000:9000", "9001:9001"]
    volumes: [miniodata:/data]
    healthcheck:
      test: ["CMD", "mc", "ready", "local"]
      interval: 5s
      retries: 10
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
  mailpit:
    image: axllent/mailpit:v1.21
    ports: ["1025:1025", "8025:8025"]
volumes:
  pgdata:
  pgtestdata:
  miniodata:
```

`infra/.env.example` contiene exactamente las variables de `Settings` con los valores locales anteriores.

`backend/tests/conftest.py`:
```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.infra.config import get_settings
from app.infra.db import Base

@pytest.fixture(scope="session")
def test_engine():
    engine = create_engine(get_settings().test_database_url)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()

@pytest.fixture
def db(test_engine):
    testing_session = sessionmaker(bind=test_engine, expire_on_commit=False)
    with testing_session() as session:
        yield session
        session.rollback()
```

`backend/README.md` documenta: `docker compose -f infra/docker-compose.yml up -d`, `cd backend && pip install -e '.[dev]'`, `pytest -v`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_health.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add infra backend && git commit -m "feat: add local infra, settings and health endpoint"
```

---

### Task 2: Modelos de catálogos, alumnos, usuarios y solicitudes

**Files:**
- Create: `backend/app/catalogos/__init__.py`, `backend/app/catalogos/models.py`, `backend/app/alumnos/__init__.py`, `backend/app/alumnos/models.py`, `backend/app/auth/__init__.py`, `backend/app/auth/models.py`, `backend/app/solicitudes/__init__.py`, `backend/app/solicitudes/models.py`, `backend/app/solicitudes/state.py`, `backend/tests/test_schema.py`
- Modify: `backend/app/main.py`

**Interfaces:**
- Consumes: `Base` de Task 1.
- Produces: clases `Convocatoria`, `Carrera`, `TipoDocumento`, `RequisitoDocumental`, `Alumno`, `Usuario`, `Solicitud`; `ALLOWED_TRANSITIONS: dict[str, set[str]]`, `InvalidTransition`, `transition(actual: str, nuevo: str) -> str`.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_schema.py`:
```python
import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.alumnos.models import Alumno
from app.catalogos.models import Carrera, Convocatoria, TipoDocumento
from app.solicitudes.models import Solicitud
from app.solicitudes.state import InvalidTransition, transition


def test_dni_unico_por_convocatoria(db: Session):
    conv = Convocatoria(nombre="2026", anio=2026, activa=True)
    carrera = Carrera(nombre="Economía", codigo="ECO", activa=True)
    alumno = Alumno(apellido="Pérez", nombres="Juan", dni="30123456",
                    email="juan@example.com", celular="+5493815555555")
    db.add_all([conv, carrera, alumno])
    db.flush()
    db.add(Solicitud(numero="FACE-2026-00001", alumno_id=alumno.id,
                     convocatoria_id=conv.id, carrera_id=carrera.id,
                     tipo_ingresante="nuevo", dni=alumno.dni, estado="BORRADOR"))
    db.flush()
    db.add(Solicitud(numero="FACE-2026-00002", alumno_id=alumno.id,
                     convocatoria_id=conv.id, carrera_id=carrera.id,
                     tipo_ingresante="nuevo", dni=alumno.dni, estado="BORRADOR"))
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_transiciones_validas():
    assert transition("RECIBIDA", "EN_VALIDACION") == "EN_VALIDACION"
    with pytest.raises(InvalidTransition):
        transition("BORRADOR", "DOCUMENTACION_APROBADA")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_schema.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'app.alumnos'`.

- [ ] **Step 3: Write minimal implementation**

`backend/app/catalogos/models.py`:
```python
from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.infra.db import Base

class Convocatoria(Base):
    __tablename__ = "convocatorias"
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120))
    anio: Mapped[int] = mapped_column(Integer)
    fecha_apertura: Mapped[str | None] = mapped_column(String(10), nullable=True)
    fecha_cierre: Mapped[str | None] = mapped_column(String(10), nullable=True)
    activa: Mapped[bool] = mapped_column(Boolean, default=True)

class Carrera(Base):
    __tablename__ = "carreras"
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120))
    codigo: Mapped[str] = mapped_column(String(20), unique=True)
    activa: Mapped[bool] = mapped_column(Boolean, default=True)

class TipoDocumento(Base):
    __tablename__ = "tipos_documentos"
    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(40), unique=True)
    nombre: Mapped[str] = mapped_column(String(120))
    descripcion: Mapped[str | None] = mapped_column(String(300), nullable=True)
    formatos: Mapped[str] = mapped_column(String(120), default="pdf,jpg,png")
    tamano_maximo_bytes: Mapped[int] = mapped_column(Integer, default=10485760)

class RequisitoDocumental(Base):
    __tablename__ = "requisitos_documentales"
    __table_args__ = (UniqueConstraint("convocatoria_id", "carrera_id",
                                       "tipo_ingresante", "tipo_documento_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    convocatoria_id: Mapped[int] = mapped_column(ForeignKey("convocatorias.id"))
    carrera_id: Mapped[int] = mapped_column(ForeignKey("carreras.id"))
    tipo_ingresante: Mapped[str] = mapped_column(String(40))
    tipo_documento_id: Mapped[int] = mapped_column(ForeignKey("tipos_documentos.id"))
    obligatorio: Mapped[bool] = mapped_column(Boolean, default=True)
```

`backend/app/alumnos/models.py`:
```python
from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from app.infra.db import Base

class Alumno(Base):
    __tablename__ = "alumnos"
    id: Mapped[int] = mapped_column(primary_key=True)
    apellido: Mapped[str] = mapped_column(String(100))
    nombres: Mapped[str] = mapped_column(String(100))
    dni: Mapped[str] = mapped_column(String(20), index=True)
    fecha_nacimiento: Mapped[str | None] = mapped_column(String(10), nullable=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    celular: Mapped[str | None] = mapped_column(String(30), nullable=True)
    domicilio: Mapped[str | None] = mapped_column(String(300), nullable=True)
    discapacidad: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

`backend/app/auth/models.py`:
```python
from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from app.infra.db import Base

class Usuario(Base):
    __tablename__ = "usuarios"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    rol: Mapped[str] = mapped_column(String(20))  # auditor | admin
    activo: Mapped[bool] = mapped_column(Boolean, default=True)

class OtpCodigo(Base):
    __tablename__ = "otp_codigos"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), index=True)
    hash_codigo: Mapped[str] = mapped_column(String(255))
    expira_en: Mapped[datetime] = mapped_column(DateTime)
    intentos: Mapped[int] = mapped_column(Integer, default=0)
    usado_en: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

`backend/app/solicitudes/models.py`:
```python
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.infra.db import Base

class Solicitud(Base):
    __tablename__ = "solicitudes"
    __table_args__ = (UniqueConstraint("convocatoria_id", "dni"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    numero: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    alumno_id: Mapped[int] = mapped_column(ForeignKey("alumnos.id"))
    convocatoria_id: Mapped[int] = mapped_column(ForeignKey("convocatorias.id"))
    carrera_id: Mapped[int] = mapped_column(ForeignKey("carreras.id"))
    tipo_ingresante: Mapped[str] = mapped_column(String(40))
    dni: Mapped[str] = mapped_column(String(20))
    estado: Mapped[str] = mapped_column(String(40), default="BORRADOR")
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

`backend/app/solicitudes/state.py`:
```python
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "BORRADOR": {"RECIBIDA", "RECHAZADA"},
    "RECIBIDA": {"EN_VALIDACION", "RECHAZADA"},
    "EN_VALIDACION": {"EN_AUDITORIA", "RECHAZADA"},
    "EN_AUDITORIA": {"DOCUMENTACION_APROBADA", "OBSERVADA", "RECHAZADA"},
    "OBSERVADA": {"PENDIENTE_ALUMNO", "RECHAZADA"},
    "PENDIENTE_ALUMNO": {"REENVIADA", "RECHAZADA"},
    "REENVIADA": {"EN_REAUDITORIA", "RECHAZADA"},
    "EN_REAUDITORIA": {"DOCUMENTACION_APROBADA", "OBSERVADA", "RECHAZADA"},
    "DOCUMENTACION_APROBADA": {"FINALIZADA", "RECHAZADA"},
    "FINALIZADA": set(),
    "RECHAZADA": set(),
}

class InvalidTransition(Exception):
    pass

def transition(actual: str, nuevo: str) -> str:
    if nuevo not in ALLOWED_TRANSITIONS.get(actual, set()):
        raise InvalidTransition(f"{actual} -> {nuevo}")
    return nuevo
```

`backend/app/main.py` agrega imports para registrar los modelos:
```python
from app import alumnos, auth, catalogos, solicitudes  # noqa: F401
```
(los cuatro módulos `__init__.py` importan sus respectivos `models`).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_schema.py -v`
Expected: PASS (2 tests). Requiere `docker compose -f ../infra/docker-compose.yml up -d postgres-test`.

- [ ] **Step 5: Commit**

```bash
git add backend && git commit -m "feat: add core models and state machine"
```

---

### Task 3: Modelos de documentos, auditorías, notificaciones e historial

**Files:**
- Create: `backend/app/documentos/__init__.py`, `backend/app/documentos/models.py`, `backend/app/auditorias/__init__.py`, `backend/app/auditorias/models.py`, `backend/app/notificaciones/__init__.py`, `backend/app/notificaciones/models.py`, `backend/tests/test_schema.py` (modificar)
- Modify: `backend/app/main.py`

**Interfaces:**
- Consumes: `Base`, `Solicitud`, `Alumno`, `Usuario`.
- Produces: `Documento`, `DocumentoVersion`, `Auditoria`, `Observacion`, `HistorialEstado`, `Notificacion`, `Consentimiento`.

- [ ] **Step 1: Write the failing test**

Agregar a `backend/tests/test_schema.py`:
```python
from sqlalchemy.exc import IntegrityError
from app.auditorias.models import Auditoria, Observacion
from app.documentos.models import Documento, DocumentoVersion
from app.notificaciones.models import HistorialEstado, Notificacion


def test_versiones_y_observaciones(db: Session):
    conv = Convocatoria(nombre="2026", anio=2026, activa=True)
    carrera = Carrera(nombre="Economía", codigo="ECO2", activa=True)
    alumno = Alumno(apellido="López", nombres="María", dni="32123456",
                    email="maria@example.com", celular="+5493815555556")
    td = TipoDocumento(codigo="dni", nombre="DNI")
    db.add_all([conv, carrera, alumno, td])
    db.flush()
    sol = Solicitud(numero="FACE-2026-00003", alumno_id=alumno.id,
                    convocatoria_id=conv.id, carrera_id=carrera.id,
                    tipo_ingresante="nuevo", dni=alumno.dni, estado="BORRADOR")
    db.add(sol)
    db.flush()
    doc = Documento(solicitud_id=sol.id, tipo_documento_id=td.id, estado="PENDIENTE")
    db.add(doc)
    db.flush()
    db.add_all([
        DocumentoVersion(documento_id=doc.id, numero=1,
                         object_key="solicitudes/3/dni/v1.pdf", mime="application/pdf",
                         bytes=1024, checksum="abc"),
        DocumentoVersion(documento_id=doc.id, numero=1,
                         object_key="solicitudes/3/dni/v1b.pdf", mime="application/pdf",
                         bytes=1024, checksum="def"),
    ])
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_idempotency_notificaciones(db: Session):
    conv = Convocatoria(nombre="2026b", anio=2026, activa=True)
    carrera = Carrera(nombre="Administración", codigo="ADM", activa=True)
    alumno = Alumno(apellido="Gómez", nombres="Pedro", dni="33123456",
                    email="pedro@example.com", celular="+5493815555557")
    db.add_all([conv, carrera, alumno])
    db.flush()
    sol = Solicitud(numero="FACE-2026-00004", alumno_id=alumno.id,
                    convocatoria_id=conv.id, carrera_id=carrera.id,
                    tipo_ingresante="nuevo", dni=alumno.dni, estado="BORRADOR")
    db.add(sol)
    db.flush()
    key = "obs|email|1|dni"
    db.add(Notificacion(solicitud_id=sol.id, evento="OBSERVADA", canal="email",
                        destinatario="pedro@example.com", estado="PENDIENTE",
                        idempotency_key=key))
    db.add(Notificacion(solicitud_id=sol.id, evento="OBSERVADA", canal="email",
                        destinatario="pedro@example.com", estado="PENDIENTE",
                        idempotency_key=key))
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_schema.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'app.documentos'`.

- [ ] **Step 3: Write minimal implementation**

`backend/app/documentos/models.py`:
```python
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.infra.db import Base

class Documento(Base):
    __tablename__ = "documentos"
    __table_args__ = (UniqueConstraint("solicitud_id", "tipo_documento_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    solicitud_id: Mapped[int] = mapped_column(ForeignKey("solicitudes.id"))
    tipo_documento_id: Mapped[int] = mapped_column(ForeignKey("tipos_documentos.id"))
    estado: Mapped[str] = mapped_column(String(30), default="PENDIENTE")
    version_vigente_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class DocumentoVersion(Base):
    __tablename__ = "documento_versiones"
    __table_args__ = (UniqueConstraint("documento_id", "numero"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    documento_id: Mapped[int] = mapped_column(ForeignKey("documentos.id"))
    numero: Mapped[int] = mapped_column(Integer)
    object_key: Mapped[str] = mapped_column(String(500))
    mime: Mapped[str] = mapped_column(String(100))
    bytes: Mapped[int] = mapped_column(Integer)
    checksum: Mapped[str] = mapped_column(String(64))
    creado_por: Mapped[str] = mapped_column(String(255))
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

`backend/app/auditorias/models.py`:
```python
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.infra.db import Base

class Auditoria(Base):
    __tablename__ = "auditorias"
    id: Mapped[int] = mapped_column(primary_key=True)
    solicitud_id: Mapped[int] = mapped_column(ForeignKey("solicitudes.id"))
    auditor_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    resultado: Mapped[str] = mapped_column(String(20))
    fecha: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    notas: Mapped[str | None] = mapped_column(Text, nullable=True)

class Observacion(Base):
    __tablename__ = "observaciones"
    id: Mapped[int] = mapped_column(primary_key=True)
    auditoria_id: Mapped[int] = mapped_column(ForeignKey("auditorias.id"))
    documento_id: Mapped[int] = mapped_column(ForeignKey("documentos.id"))
    motivo: Mapped[str] = mapped_column(Text)
    resuelta_en: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
```

`backend/app/notificaciones/models.py`:
```python
from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.infra.db import Base

class HistorialEstado(Base):
    __tablename__ = "historial_estados"
    id: Mapped[int] = mapped_column(primary_key=True)
    solicitud_id: Mapped[int] = mapped_column(ForeignKey("solicitudes.id"))
    estado_anterior: Mapped[str | None] = mapped_column(String(40), nullable=True)
    estado_nuevo: Mapped[str] = mapped_column(String(40))
    actor: Mapped[str] = mapped_column(String(255))
    fecha: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    motivo: Mapped[str | None] = mapped_column(Text, nullable=True)

class Notificacion(Base):
    __tablename__ = "notificaciones"
    id: Mapped[int] = mapped_column(primary_key=True)
    solicitud_id: Mapped[int] = mapped_column(ForeignKey("solicitudes.id"))
    evento: Mapped[str] = mapped_column(String(40))
    canal: Mapped[str] = mapped_column(String(20))
    destinatario: Mapped[str] = mapped_column(String(255))
    estado: Mapped[str] = mapped_column(String(20), default="PENDIENTE")
    asunto: Mapped[str] = mapped_column(String(200), default="Notificación FACE")
    cuerpo: Mapped[str] = mapped_column(Text, default="")
    intentos: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(255), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Consentimiento(Base):
    __tablename__ = "consentimientos"
    id: Mapped[int] = mapped_column(primary_key=True)
    alumno_id: Mapped[int] = mapped_column(ForeignKey("alumnos.id"))
    canal: Mapped[str] = mapped_column(String(20))
    aceptado: Mapped[bool] = mapped_column(Boolean)
    fecha: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

Modificar `backend/app/main.py` para registrar los nuevos modelos:
```python
from app import alumnos, auditorias, auth, catalogos, documentos, notificaciones, solicitudes  # noqa: F401
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_schema.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add backend && git commit -m "feat: add document, audit and notification models"
```

### Task 4: Migraciones Alembic

**Files:**
- Create: `backend/alembic.ini`, `backend/app/infra/migrations/env.py`, `backend/app/infra/migrations/script.py.mako`, `backend/tests/test_migraciones.py`
- Create (generado): `backend/app/infra/migrations/versions/0001_initial_schema.py`

**Interfaces:**
- Consumes: todos los modelos de Tasks 2 y 3.
- Produces: `alembic upgrade head` crea el esquema completo; `alembic current` reporta `head`.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_migraciones.py`:
```python
import subprocess
from sqlalchemy import inspect, text
from app.infra.config import get_settings
from app.infra.db import Base

TABLAS = {
    "alumnos", "auditorias", "consentimientos", "convocatorias", "carreras",
    "documento_versiones", "documentos", "historial_estados", "notificaciones",
    "observaciones", "otp_codigos", "requisitos_documentales", "solicitudes",
    "tipos_documentos", "usuarios",
}


def test_migracion_crea_todas_las_tablas(test_engine):
    Base.metadata.drop_all(test_engine)
    with test_engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
        conn.commit()
    subprocess.run(
        ["alembic", "upgrade", "head"],
        cwd="backend", check=True,
        env={"PATH": "/usr/bin:/bin:/usr/local/bin",
             "DATABASE_URL": get_settings().test_database_url},
        capture_output=True,
    )
    tablas = set(inspect(test_engine).get_table_names())
    assert TABLAS <= tablas
    with test_engine.connect() as conn:
        assert conn.execute(text("SELECT 1 FROM alembic_version")).scalar() is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_migraciones.py -v`
Expected: FAIL porque `alembic.ini` no existe.

- [ ] **Step 3: Write minimal implementation**

`backend/alembic.ini` con `script_location = app/infra/migrations` y `sqlalchemy.url =` vacío (se inyecta por entorno).

`backend/app/infra/migrations/env.py`:
```python
from logging.config import fileConfig
from alembic import context
from sqlalchemy import create_engine, pool
from app.infra.config import get_settings
from app.infra.db import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
config.set_main_option("sqlalchemy.url", get_settings().database_url.replace("%", "%%"))
target_metadata = Base.metadata


def run_migrations_online() -> None:
    engine = create_engine(config.get_main_option("sqlalchemy.url"), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata,
                          compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
```

`backend/app/infra/migrations/script.py.mako` es la plantilla estándar de Alembic con `${up_revision}`, `${down_revision}` y `${upgrades}` / `${downgrades}`.

Luego ejecutar, con `DATABASE_URL` apuntando a la BD de pruebas:
```bash
cd backend && DATABASE_URL="postgresql+psycopg://face:face@localhost:5433/face_test" \
  alembic revision --autogenerate -m "initial schema"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_migraciones.py -v`
Expected: PASS; la revisión generada contiene las 15 tablas.

- [ ] **Step 5: Commit**

```bash
git add backend && git commit -m "feat: add alembic initial migration"
```

---

### Task 5: Autenticación OTP y usuarios administrativos

**Files:**
- Create: `backend/app/auth/schemas.py`, `backend/app/auth/service.py`, `backend/app/auth/router.py`, `backend/app/infra/email.py`, `backend/tests/test_auth.py`
- Modify: `backend/app/main.py`

**Interfaces:**
- Consumes: `OtpCodigo`, `Usuario`, `Settings`.
- Produces: `request_otp(db: Session, email: str, sender: EmailSender) -> None`, `verify_otp(db: Session, email: str, code: str) -> str`, `authenticate_admin(db: Session, email: str, password: str) -> str`, routers incluidos en `/auth`.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_auth.py`:
```python
from datetime import datetime, timedelta
import jwt
from sqlalchemy.orm import Session
from app.auth.models import OtpCodigo, Usuario
from app.auth.service import request_otp, verify_otp, authenticate_admin
from app.infra.config import get_settings

class FakeSender:
    def __init__(self):
        self.mensajes = []
    def send(self, to, subject, body):
        self.mensajes.append((to, subject, body))

from passlib.context import CryptContext
crypt = CryptContext(schemes=["bcrypt"])


def test_otp_ciclo_completo(db: Session):
    sender = FakeSender()
    request_otp(db, "ana@example.com", sender)
    assert len(sender.mensajes) == 1
    fila = db.query(OtpCodigo).filter_by(email="ana@example.com").one()
    fila.expira_en = datetime.utcnow() + timedelta(minutes=10)
    db.commit()
    import re
    code = re.search(r"\b\d{6}\b", sender.mensajes[0][2]).group(0)
    token = verify_otp(db, "ana@example.com", code)
    payload = jwt.decode(token, get_settings().secret_key, algorithms=["HS256"])
    assert payload["sub"] == "ana@example.com"


def test_otp_rechaza_codigo_incorrecto(db: Session):
    sender = FakeSender()
    request_otp(db, " Luis@example.com ".strip().lower(), sender)
    try:
        verify_otp(db, "luis@example.com", "000000")
    except ValueError as exc:
        assert "inválido" in str(exc)
    else:
        raise AssertionError("debió fallar")


def test_login_admin(db: Session):
    db.add(Usuario(email="admin@face.unt.edu.ar",
                   password_hash=crypt.hash("clave-secreta"),
                   rol="admin", activo=True))
    db.commit()
    token = authenticate_admin(db, "admin@face.unt.edu.ar", "clave-secreta")
    assert jwt.decode(token, get_settings().secret_key, algorithms=["HS256"])["rol"] == "admin"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_auth.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'app.auth.service'`.

- [ ] **Step 3: Write minimal implementation**

`backend/app/infra/email.py`:
```python
import smtplib
from email.message import EmailMessage
from app.infra.config import Settings

class EmailSender:
    def __init__(self, settings: Settings):
        self.settings = settings
    def send(self, to: str, subject: str, body: str) -> None:
        msg = EmailMessage()
        msg["From"] = "preinscripcion@face.unt.edu.ar"
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)
        with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port) as smtp:
            smtp.send_message(msg)
```

`backend/app/auth/service.py`:
```python
import hashlib
import secrets
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import jwt
from passlib.context import CryptContext
from app.auth.models import OtpCodigo, Usuario
from app.infra.config import get_settings

crypt = CryptContext(schemes=["bcrypt"])

def _hash(code: str) -> str:
    return hashlib.sha256(f"{get_settings().secret_key}:{code}".encode()).hexdigest()

def request_otp(db: Session, email: str, sender) -> None:
    email = email.strip().lower()
    code = f"{secrets.randbelow(1000000):06d}"
    s = get_settings()
    db.add(OtpCodigo(email=email, hash_codigo=_hash(code),
                     expira_en=datetime.utcnow() + timedelta(seconds=s.otp_ttl_seconds)))
    db.commit()
    sender.send(email, "Código de verificación FACE",
                f"Su código de verificación es {code}. Vence en {s.otp_ttl_seconds} segundos.")

def verify_otp(db: Session, email: str, code: str) -> str:
    email = email.strip().lower()
    row = db.query(OtpCodigo).filter_by(email=email).order_by(OtpCodigo.id.desc()).first()
    if row is None or row.usado_en or row.expira_en < datetime.utcnow() \
            or row.intentos >= get_settings().otp_max_intentos:
        raise ValueError("código inválido o vencido")
    if row.hash_codigo != _hash(code):
        row.intentos += 1
        db.commit()
        raise ValueError("código inválido")
    row.usado_en = datetime.utcnow()
    db.commit()
    s = get_settings()
    return jwt.encode({"sub": email}, s.secret_key, algorithm="HS256")

def authenticate_admin(db: Session, email: str, password: str) -> str:
    user = db.query(Usuario).filter_by(email=email.strip().lower(), activo=True).first()
    if user is None or not crypt.verify(password, user.password_hash):
        raise ValueError("credenciales inválidas")
    s = get_settings()
    return jwt.encode({"sub": user.email, "rol": user.rol}, s.secret_key, algorithm="HS256")
```

`backend/app/auth/router.py`:
```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from app.auth import service
from app.infra.config import get_settings
from app.infra.db import get_db
from app.infra.email import EmailSender

router = APIRouter(prefix="/auth", tags=["auth"])

class OtpRequest(BaseModel):
    email: EmailStr

class OtpVerify(OtpRequest):
    code: str

class AdminLogin(BaseModel):
    email: EmailStr
    password: str

@router.post("/request-otp", status_code=202)
def request_otp(data: OtpRequest, db: Session = Depends(get_db)):
    service.request_otp(db, data.email, EmailSender(get_settings()))
    return {"detail": "código enviado"}

@router.post("/verify-otp")
def verify_otp(data: OtpVerify, db: Session = Depends(get_db)):
    try:
        token = service.verify_otp(db, data.email, data.code)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"access_token": token, "token_type": "bearer"}

@router.post("/admin/login")
def admin_login(data: AdminLogin, db: Session = Depends(get_db)):
    try:
        token = service.authenticate_admin(db, data.email, data.password)
    except ValueError as exc:
        raise HTTPException(401, str(exc)) from exc
    return {"access_token": token, "token_type": "bearer"}
```

`backend/app/main.py` agrega:
```python
from app.auth.router import router as auth_router
app.include_router(auth_router)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_auth.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add backend && git commit -m "feat: add email OTP and admin login"
```

---

### Task 6: Catálogos configurables y datos semilla

**Files:**
- Create: `backend/app/catalogos/router.py`, `backend/app/catalogos/seed.py`, `backend/tests/test_catalogos.py`
- Modify: `backend/app/main.py`

**Interfaces:**
- Consumes: `Convocatoria`, `Carrera`, `TipoDocumento`, `RequisitoDocumental`.
- Produces: `seed_catalogos(db: Session) -> None` (idempotente), endpoints `GET /catalogos/convocatorias`, `GET /catalogos/carreras`, `GET /catalogos/tipos-documentos`, `GET /catalogos/requisitos?convocatoria_id=&carrera_id=&tipo_ingresante=`.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_catalogos.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_catalogos.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'app.catalogos.seed'`.

- [ ] **Step 3: Write minimal implementation**

`backend/app/catalogos/seed.py`:
```python
from sqlalchemy.orm import Session
from app.catalogos.models import Carrera, Convocatoria, RequisitoDocumental, TipoDocumento

TIPOS = [
    ("dni", "DNI", "Frente y dorso, color y legible"),
    ("foto_carnet", "Foto carnet", "Fondo claro, frente y perfil derecho"),
    ("acta_nacimiento", "Acta de nacimiento", "Actualizada, legalizada y de ambos lados"),
    ("titulo_secundario", "Título secundario", "Título o constancia sin materias adeudadas"),
    ("formulario_siu", "Formulario SIU Guaraní", "Formulario de preinscripción obtenido de SIU"),
    ("comprobante_pago", "Comprobante de pago", "Imagen o PDF legible"),
]
CARRERAS = [("Contador Público", "CP"), ("Economía", "ECO"), ("Administración", "ADM")]

def seed_catalogos(db: Session) -> None:
    if db.query(Convocatoria).first() is not None:
        return
    conv = Convocatoria(nombre="Convocatoria 2026", anio=2026, activa=True)
    db.add(conv)
    db.flush()
    tipos = [TipoDocumento(codigo=c, nombre=n, descripcion=d) for c, n, d in TIPOS]
    carreras = [Carrera(nombre=n, codigo=c, activa=True) for n, c in CARRERAS]
    db.add_all(tipos + carreras)
    db.flush()
    db.add_all(RequisitoDocumental(
        convocatoria_id=conv.id, carrera_id=car.id,
        tipo_ingresante="nuevo", tipo_documento_id=td.id, obligatorio=True,
    ) for car in carreras for td in tipos)
    db.commit()
```

`backend/app/catalogos/router.py`:
```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.catalogos.models import Carrera, Convocatoria, RequisitoDocumental, TipoDocumento
from app.infra.db import get_db

router = APIRouter(prefix="/catalogos", tags=["catalogos"])

class ConvocatoriaOut(BaseModel):
    id: int
    nombre: str
    anio: int
    activa: bool
    model_config = {"from_attributes": True}

class CarreraOut(BaseModel):
    id: int
    nombre: str
    codigo: str
    activa: bool
    model_config = {"from_attributes": True}

class TipoDocumentoOut(BaseModel):
    id: int
    codigo: str
    nombre: str
    descripcion: str | None
    formatos: str
    tamano_maximo_bytes: int
    model_config = {"from_attributes": True}

class RequisitoOut(BaseModel):
    id: int
    convocatoria_id: int
    carrera_id: int
    tipo_ingresante: str
    tipo_documento_id: int
    obligatorio: bool
    model_config = {"from_attributes": True}

@router.get("/convocatorias", response_model=list[ConvocatoriaOut])
def convocatorias(db: Session = Depends(get_db)):
    return db.query(Convocatoria).filter_by(activa=True).all()

@router.get("/carreras", response_model=list[CarreraOut])
def carreras(db: Session = Depends(get_db)):
    return db.query(Carrera).filter_by(activa=True).all()

@router.get("/tipos-documentos", response_model=list[TipoDocumentoOut])
def tipos_documentos(db: Session = Depends(get_db)):
    return db.query(TipoDocumento).all()

@router.get("/requisitos", response_model=list[RequisitoOut])
def requisitos(convocatoria_id: int, carrera_id: int,
               tipo_ingresante: str, db: Session = Depends(get_db)):
    return db.query(RequisitoDocumental).filter_by(
        convocatoria_id=convocatoria_id, carrera_id=carrera_id,
        tipo_ingresante=tipo_ingresante).all()
```

`backend/app/main.py`:
```python
from app.catalogos.router import router as catalogos_router
from app.catalogos.seed import seed_catalogos
app.include_router(catalogos_router)

@app.on_event("startup")
def startup_seed():
    with SessionLocal() as db:
        seed_catalogos(db)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_catalogos.py -v`
Expected: PASS (1 test).

- [ ] **Step 5: Commit**

```bash
git add backend && git commit -m "feat: add configurable catalogs and seed data"
```

---

### Task 7: Solicitudes, borrador, confirmación e historial

**Files:**
- Create: `backend/app/solicitudes/schemas.py`, `backend/app/solicitudes/service.py`, `backend/app/solicitudes/router.py`, `backend/tests/test_solicitudes.py`
- Modify: `backend/app/main.py`

**Interfaces:**
- Consumes: `Solicitud`, `Alumno`, `Documento`, `RequisitoDocumental`, `transition`, `HistorialEstado`.
- Produces: `crear_borrador(db, email, payload) -> Solicitud`, `confirmar(db, solicitud_id, version) -> Solicitud`, `registrar_transicion(db, solicitud, nuevo_estado, actor, motivo=None) -> Solicitud`, `GET/POST /solicitudes`, `POST /solicitudes/{id}/confirmar`.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_solicitudes.py`:
```python
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.alumnos.models import Alumno
from app.catalogos.models import Carrera, Convocatoria
from app.catalogos.seed import seed_catalogos
from app.infra.db import get_db
from app.solicitudes.router import router
from app.solicitudes.service import crear_borrador, confirmar
from app.solicitudes.state import InvalidTransition


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_solicitudes.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'app.solicitudes.service'`.

- [ ] **Step 3: Write minimal implementation**

`backend/app/solicitudes/service.py`:
```python
from sqlalchemy import func, text
from sqlalchemy.orm import Session
from app.alumnos.models import Alumno
from app.catalogos.models import Convocatoria, RequisitoDocumental
from app.documentos.models import Documento
from app.notificaciones.models import HistorialEstado
from app.solicitudes.models import Solicitud
from app.solicitudes.state import transition

class VersioObsoleta(Exception):
    pass

def _siguiente_numero(db: Session, anio: int, convocatoria_id: int) -> str:
    if not db.execute(text("SELECT to_regclass('solicitud_numero_seq')")).scalar():
        db.execute(text("CREATE SEQUENCE solicitud_numero_seq START 1"))
        db.commit()
    n = db.execute(text("SELECT nextval('solicitud_numero_seq')")).scalar()
    return f"FACE-{anio}-{n:05d}"

def registrar_transicion(db: Session, sol: Solicitud, nuevo: str,
                         actor: str, motivo: str | None = None) -> Solicitud:
    anterior = sol.estado
    sol.estado = transition(anterior, nuevo)
    sol.version += 1
    db.add(HistorialEstado(solicitud_id=sol.id, estado_anterior=anterior,
                           estado_nuevo=nuevo, actor=actor, motivo=motivo))
    db.commit()
    return sol

def crear_borrador(db: Session, email: str, data: dict) -> Solicitud:
    alumno = db.query(Alumno).filter_by(email=email.strip().lower()).first()
    if alumno is None:
        alumno = Alumno(apellido=data["apellido"], nombres=data["nombres"],
                        dni=data["dni"], fecha_nacimiento=data.get("fecha_nacimiento"),
                        email=email.strip().lower(), celular=data.get("celular"),
                        domicilio=data.get("domicilio"),
                        discapacidad=bool(data.get("discapacidad", False)))
        db.add(alumno)
        db.flush()
    conv = db.get(Convocatoria, data["convocatoria_id"])
    sol = Solicitud(numero=None, alumno_id=alumno.id, convocatoria_id=conv.id,
                    carrera_id=data["carrera_id"],
                    tipo_ingresante=data["tipo_ingresante"],
                    dni=alumno.dni, estado="BORRADOR")
    db.add(sol)
    db.commit()
    return sol

def confirmar(db: Session, solicitud_id: int, version: int,
              on_confirm=None) -> Solicitud:
    sol = db.get(Solicitud, solicitud_id)
    if sol is None:
        raise ValueError("solicitud no encontrada")
    if sol.version != version:
        raise ValueError("versión obsoleta")
    requisitos = db.query(RequisitoDocumental).filter_by(
        convocatoria_id=sol.convocatoria_id, carrera_id=sol.carrera_id,
        tipo_ingresante=sol.tipo_ingresante, obligatorio=True).all()
    ids = {r.tipo_documento_id for r in requisitos}
    cargados = {d.tipo_documento_id for d in db.query(Documento).filter_by(
        solicitud_id=sol.id).all() if d.estado != "PENDIENTE"}
    if ids - cargados:
        raise ValueError(f"requisitos pendientes: {sorted(ids - cargados)}")
    conv = db.get(Convocatoria, sol.convocatoria_id)
    sol.numero = _siguiente_numero(db, conv.anio, conv.id)
    db.commit()
    sol = registrar_transicion(db, sol, "RECIBIDA", "alumno")
    if on_confirm is not None:
        on_confirm(sol.id)
    return sol
```

`backend/app/solicitudes/router.py`:
```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from app.infra.db import get_db
from app.solicitudes import service
from app.solicitudes.models import Solicitud

router = APIRouter(prefix="/solicitudes", tags=["solicitudes"])

class SolicitudIn(BaseModel):
    apellido: str
    nombres: str
    dni: str
    email: EmailStr
    celular: str
    fecha_nacimiento: str | None = None
    domicilio: str | None = None
    discapacidad: bool = False
    convocatoria_id: int
    carrera_id: int
    tipo_ingresante: str

class ConfirmarIn(BaseModel):
    version: int

@router.post("")
def crear(data: SolicitudIn, db: Session = Depends(get_db)):
    return service.crear_borrador(db, data.email, data.model_dump())

@router.get("/mia")
def mia(email: EmailStr, db: Session = Depends(get_db)):
    sol = (db.query(Solicitud).join(Alumno)
           .filter(Alumno.email == email).order_by(Solicitud.id.desc()).first())
    if sol is None:
        raise HTTPException(404, "solicitud no encontrada")
    return sol

@router.get("/{solicitud_id}")
def obtener(solicitud_id: int, db: Session = Depends(get_db)):
    sol = db.get(Solicitud, solicitud_id)
    if sol is None:
        raise HTTPException(404, "solicitud no encontrada")
    return sol

@router.post("/{solicitud_id}/confirmar")
def confirmar(solicitud_id: int, data: ConfirmarIn, db: Session = Depends(get_db)):
    try:
        sol = service.confirmar(db, solicitud_id, data.version)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"numero": sol.numero, "fecha": sol.updated_at,
            "estado": sol.estado, "comprobante": f"Recibido {sol.numero}"}
```
(con `Alumno` importado de `app.alumnos.models`). El callback `on_confirm` se agrega en Task 8.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_solicitudes.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add backend && git commit -m "feat: add application lifecycle and history"
```

### Task 8: MinIO privado, carga de documentos y validación automática

**Files:**
- Create: `backend/app/infra/storage.py`, `backend/app/infra/celery_app.py`, `backend/app/documentos/schemas.py`, `backend/app/documentos/service.py`, `backend/app/documentos/router.py`, `backend/worker/__init__.py`, `backend/worker/tasks.py`, `backend/tests/test_documentos.py`
- Modify: `backend/app/main.py`, `backend/app/solicitudes/router.py`

**Interfaces:**
- Consumes: `Documento`, `DocumentoVersion`, `TipoDocumento`, `registrar_transicion`, `Settings`.
- Produces: `ObjectStore` (`presigned_put`, `presigned_get`, `put_bytes`, `get_bytes`, `exists`), `registrar_documento(db, solicitud_id, tipo_documento_id, filename, content_type, size, checksum, creado_por, store) -> Documento`, `validar_version(db, version_id, store) -> DocumentoVersion`, `validar_documentos_solicitud(solicitud_id)`, `celery_app`.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_documentos.py`:
```python
import hashlib
import pytest
from sqlalchemy.orm import Session
from app.alumnos.models import Alumno
from app.catalogos.models import Carrera, Convocatoria, TipoDocumento
from app.documentos.models import Documento, DocumentoVersion
from app.documentos.service import registrar_documento, validar_version
from app.solicitudes.models import Solicitud

class FakeStore:
    def __init__(self):
        self.objects = {}
    def put_bytes(self, key, data):
        self.objects[key] = data
    def get_bytes(self, key):
        return self.objects[key]
    def exists(self, key):
        return key in self.objects
    def presigned_put(self, key, content_type, expires):
        return f"http://minio/{key}?X-Amz-Expires={expires}"
    def presigned_get(self, key, expires):
        return f"http://minio/{key}?X-Amz-Expires={expires}"


@pytest.fixture
def contexto(db: Session):
    conv = Convocatoria(nombre="2026-doc", anio=2026, activa=True)
    car = Carrera(nombre="Economía", codigo="ECOD", activa=True)
    alumno = Alumno(apellido="Pérez", nombres="Ana", dni="30123456",
                    email="ana-doc@example.com", celular="+5493815555555")
    td = TipoDocumento(codigo="dni", nombre="DNI",
                       formatos="pdf,jpg,png", tamano_maximo_bytes=10485760)
    db.add_all([conv, car, alumno, td])
    db.flush()
    sol = Solicitud(numero="FACE-2026-90001", alumno_id=alumno.id,
                    convocatoria_id=conv.id, carrera_id=car.id,
                    tipo_ingresante="nuevo", dni=alumno.dni, estado="RECIBIDA")
    db.add(sol)
    db.commit()
    return sol, td, FakeStore()


def test_registro_y_validacion(contexto, db: Session):
    sol, td, store = contexto
    data = b"contenido del dni"
    checksum = hashlib.sha256(data).hexdigest()
    doc = registrar_documento(db, sol.id, td.id, "dni.pdf", "application/pdf",
                              len(data), checksum, "ana-doc@example.com", store)
    assert doc.estado == "RECIBIDO"
    version = db.query(DocumentoVersion).filter_by(documento_id=doc.id).one()
    assert version.object_key.startswith(f"solicitudes/{sol.id}/dni/v1.")
    store.put_bytes(version.object_key, data)
    validar_version(db, version.id, store)
    assert db.get(Documento, doc.id).estado == "EN_REVISION"


def test_rechaza_formato_y_tamano(contexto, db: Session):
    sol, td, store = contexto
    with pytest.raises(ValueError, match="formato no permitido"):
        registrar_documento(db, sol.id, td.id, "dni.gif", "image/gif", 10, "x",
                            "ana-doc@example.com", store)
    with pytest.raises(ValueError, match="archivo demasiado grande"):
        registrar_documento(db, sol.id, td.id, "dni.pdf", "application/pdf",
                            10485761, "x", "ana-doc@example.com", store)


def test_checksum_invalido(contexto, db: Session):
    sol, td, store = contexto
    doc = registrar_documento(db, sol.id, td.id, "dni.pdf", "application/pdf",
                              4, "mal checksum", "ana-doc@example.com", store)
    version = db.query(DocumentoVersion).filter_by(documento_id=doc.id).one()
    store.put_bytes(version.object_key, b"abcd")
    with pytest.raises(ValueError, match="checksum"):
        validar_version(db, version.id, store)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_documentos.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'app.infra.storage'`.

- [ ] **Step 3: Write minimal implementation**

`backend/app/infra/storage.py`:
```python
from minio import Minio
from app.infra.config import Settings

class ObjectStore:
    def __init__(self, settings: Settings):
        self.bucket = settings.minio_bucket
        self.client = Minio(settings.minio_endpoint,
                            access_key=settings.minio_access_key,
                            secret_key=settings.minio_secret_key, secure=False)
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)
    def put_bytes(self, key: str, data: bytes) -> None:
        from io import BytesIO
        self.client.put_object(self.bucket, key, BytesIO(data), len(data))
    def get_bytes(self, key: str) -> bytes:
        response = self.client.get_object(self.bucket, key)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()
    def exists(self, key: str) -> bool:
        try:
            self.client.stat_object(self.bucket, key)
            return True
        except Exception:
            return False
    def presigned_put(self, key: str, content_type: str, expires: int) -> str:
        return self.client.presigned_put_object(self.bucket, key, expires=expires)
    def presigned_get(self, key: str, expires: int) -> str:
        return self.client.presigned_get_object(self.bucket, key, expires=expires)
```

`backend/app/infra/celery_app.py`:
```python
from celery import Celery
from app.infra.config import get_settings

celery_app = Celery("face", broker=get_settings().redis_url,
                    backend=get_settings().redis_url)
celery_app.conf.update(task_track_started=True, task_acks_late=True)
```

`backend/app/documentos/service.py`:
```python
import hashlib
from sqlalchemy.orm import Session
from app.catalogos.models import TipoDocumento
from app.documentos.models import Documento, DocumentoVersion
from app.infra.db import SessionLocal
from app.solicitudes.models import Solicitud
from app.solicitudes.service import registrar_transicion

EXTENSIONES = {"application/pdf": "pdf", "image/jpeg": "jpg", "image/png": "png"}

def registrar_documento(db: Session, solicitud_id: int, tipo_documento_id: int,
                        filename: str, content_type: str, size: int, checksum: str,
                        creado_por: str, store) -> Documento:
    td = db.get(TipoDocumento, tipo_documento_id)
    if content_type not in EXTENSIONES:
        raise ValueError("formato no permitido")
    if size > td.tamano_maximo_bytes:
        raise ValueError("archivo demasiado grande")
    doc = db.query(Documento).filter_by(
        solicitud_id=solicitud_id, tipo_documento_id=tipo_documento_id).one_or_none()
    if doc is None:
        doc = Documento(solicitud_id=solicitud_id, tipo_documento_id=tipo_documento_id,
                        estado="RECIBIDO")
        db.add(doc)
        db.flush()
    elif doc.estado in ("APROBADO", "OBSERVADO", "REEMPLAZADO"):
        doc.estado = "REEMPLAZADO"
    numero = doc.version + 1
    key = f"solicitudes/{solicitud_id}/{td.codigo}/v{numero}.{EXTENSIONES[content_type]}"
    db.add(DocumentoVersion(documento_id=doc.id, numero=numero, object_key=key,
                            mime=content_type, bytes=size, checksum=checksum,
                            creado_por=creado_por))
    doc.version = numero
    doc.version_vigente_id = None
    db.commit()
    return doc

def validar_version(db: Session, version_id: int, store) -> DocumentoVersion:
    version = db.get(DocumentoVersion, version_id)
    data = store.get_bytes(version.object_key)
    if hashlib.sha256(data).hexdigest() != version.checksum:
        raise ValueError("checksum no coincide")
    if len(data) != version.bytes:
        raise ValueError("tamaño no coincide")
    doc = db.get(Documento, version.documento_id)
    doc.estado = "EN_REVISION"
    doc.version_vigente_id = version.id
    db.commit()
    return version

def validar_documentos_solicitud(solicitud_id: int) -> None:
    with SessionLocal() as db:
        from app.infra.config import get_settings
        from app.infra.storage import ObjectStore
        store = ObjectStore(get_settings())
        sol = db.get(Solicitud, solicitud_id)
        if sol.estado == "RECIBIDA":
            registrar_transicion(db, sol, "EN_VALIDACION", "worker")
        documentos = db.query(Documento).filter_by(solicitud_id=solicitud_id).all()
        for doc in documentos:
            version = db.query(DocumentoVersion).filter_by(
                documento_id=doc.id, numero=doc.version).one()
            validar_version(db, version.id, store)
        if sol.estado == "EN_VALIDACION":
            registrar_transicion(db, sol, "EN_AUDITORIA", "worker")
```

`backend/worker/tasks.py`:
```python
from app.documentos.service import validar_documentos_solicitud as _validar
from app.infra.celery_app import celery_app

@celery_app.task(name="documentos.validar_solicitud", bind=True, max_retries=3)
def validar_documentos_solicitud(self, solicitud_id: int):
    try:
        _validar(solicitud_id)
    except Exception as exc:
        raise self.retry(exc=exc, countdown=30)
```

`backend/app/documentos/router.py`:
```python
import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.documentos.models import Documento, DocumentoVersion
from app.documentos.service import registrar_documento, validar_version
from app.infra.config import get_settings
from app.infra.db import get_db
from app.infra.storage import ObjectStore

router = APIRouter(prefix="/documentos", tags=["documentos"])
logger = logging.getLogger("acceso-documentos")

class UploadUrlIn(BaseModel):
    solicitud_id: int
    tipo_documento_id: int
    filename: str
    content_type: str
    size: int
    checksum: str

def get_store():
    return ObjectStore(get_settings())

@router.post("/upload-url")
def upload_url(data: UploadUrlIn, db: Session = Depends(get_db),
               store: ObjectStore = Depends(get_store)):
    try:
        doc = registrar_documento(db, data.solicitud_id, data.tipo_documento_id,
                                  data.filename, data.content_type, data.size,
                                  data.checksum, "alumno", store)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    version = db.query(DocumentoVersion).filter_by(
        documento_id=doc.id, numero=doc.version).one()
    url = store.presigned_put(version.object_key, data.content_type,
                              get_settings().upload_url_ttl)
    return {"url": url, "expires_in": get_settings().upload_url_ttl,
            "documento_id": doc.id}

@router.get("/{documento_id}/download-url")
def download_url(documento_id: int, db: Session = Depends(get_db),
                 store: ObjectStore = Depends(get_store)):
    doc = db.get(Documento, documento_id)
    if doc is None or doc.version_vigente_id is None:
        raise HTTPException(404, "versión vigente no encontrada")
    version = db.get(DocumentoVersion, doc.version_vigente_id)
    logger.info("descarga documento_id=%s object_key=%s", documento_id,
                version.object_key)
    url = store.presigned_get(version.object_key, get_settings().download_url_ttl)
    return {"url": url, "expires_in": get_settings().download_url_ttl}

@router.post("/{version_id}/validar")
def validar(version_id: int, db: Session = Depends(get_db),
            store: ObjectStore = Depends(get_store)):
    try:
        version = validar_version(db, version_id, store)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"object_key": version.object_key, "estado": "EN_REVISION"}
```

`backend/app/main.py` agrega `from app.documentos.router import router as documentos_router` y `app.include_router(documentos_router)`.

`backend/app/solicitudes/router.py` modifica el handler de confirmación para pasar `on_confirm=validar_documentos_solicitud.delay`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_documentos.py -v`
Expected: PASS (3 tests). Requiere MinIO levantado para el test de integración real; el test unitario usa `FakeStore`.

- [ ] **Step 5: Commit**

```bash
git add backend && git commit -m "feat: add MinIO uploads and automatic validation"
```

---

### Task 9: Auditoría documental con observaciones por documento

**Files:**
- Create: `backend/app/auditorias/schemas.py`, `backend/app/auditorias/service.py`, `backend/app/auditorias/router.py`, `backend/tests/test_auditorias.py`
- El router se registra en `main.py` recién en Task 11, cuando `publicar_evento` existe.

**Interfaces:**
- Consumes: `Auditoria`, `Observacion`, `Documento`, `registrar_transicion`.
- Produces: `registrar_auditoria(db, solicitud_id, auditor_id, decisiones, on_event=None) -> Auditoria`.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_auditorias.py`:
```python
import pytest
from sqlalchemy.orm import Session
from app.alumnos.models import Alumno
from app.auditorias.models import Observacion
from app.auditorias.service import registrar_auditoria
from app.catalogos.models import Carrera, Convocatoria, TipoDocumento
from app.documentos.models import Documento
from app.solicitudes.models import Solicitud

@pytest.fixture
def solicitud_en_auditoria(db: Session):
    conv = Convocatoria(nombre="2026-aud", anio=2026, activa=True)
    car = Carrera(nombre="Economía", codigo="ECOA", activa=True)
    alumno = Alumno(apellido="López", nombres="María", dni="32123456",
                    email="maria-aud@example.com", celular="+5493815555555")
    td = TipoDocumento(codigo="dni", nombre="DNI")
    db.add_all([conv, car, alumno, td])
    db.flush()
    sol = Solicitud(numero="FACE-2026-90002", alumno_id=alumno.id,
                    convocatoria_id=conv.id, carrera_id=car.id,
                    tipo_ingresante="nuevo", dni=alumno.dni, estado="EN_AUDITORIA")
    db.add(sol)
    db.flush()
    doc = Documento(solicitud_id=sol.id, tipo_documento_id=td.id, estado="EN_REVISION")
    db.add(doc)
    db.commit()
    return sol, doc, 1


def test_observacion_cambia_estado(solicitud_en_auditoria, db: Session):
    sol, doc, auditor_id = solicitud_en_auditoria
    eventos = []
    registrar_auditoria(db, sol.id, auditor_id,
                        [{"documento_id": doc.id, "resultado": "OBSERVADO",
                          "motivo": "El reverso del DNI es ilegible."}],
                        on_event=lambda evento, datos: eventos.append(evento))
    assert sol.estado == "PENDIENTE_ALUMNO"
    assert db.query(Observacion).filter_by(documento_id=doc.id).count() == 1
    assert eventos == ["OBSERVADA"]


def test_aprobacion_total(solicitud_en_auditoria, db: Session):
    sol, doc, auditor_id = solicitud_en_auditoria
    eventos = []
    registrar_auditoria(db, sol.id, auditor_id,
                        [{"documento_id": doc.id, "resultado": "APROBADO"}],
                        on_event=lambda evento, datos: eventos.append(evento))
    assert sol.estado == "DOCUMENTACION_APROBADA"
    assert db.get(Documento, doc.id).estado == "APROBADO"
    assert eventos == ["DOCUMENTACION_APROBADA"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_auditorias.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'app.auditorias.service'`.

- [ ] **Step 3: Write minimal implementation**

`backend/app/auditorias/service.py`:
```python
from sqlalchemy.orm import Session
from app.auditorias.models import Auditoria, Observacion
from app.catalogos.models import TipoDocumento
from app.documentos.models import Documento
from app.solicitudes.models import Solicitud
from app.solicitudes.service import registrar_transicion

def registrar_auditoria(db: Session, solicitud_id: int, auditor_id: int,
                        decisiones: list[dict], on_event=None) -> Auditoria:
    sol = db.get(Solicitud, solicitud_id)
    if sol.estado not in ("EN_AUDITORIA", "EN_REAUDITORIA"):
        raise ValueError(f"estado no auditable: {sol.estado}")
    if not decisiones:
        raise ValueError("debe auditar al menos un documento")
    audit = Auditoria(solicitud_id=solicitud_id, auditor_id=auditor_id,
                      resultado="APROBADO")
    db.add(audit)
    db.flush()
    observados = []
    for decision in decisiones:
        doc = db.get(Documento, decision["documento_id"])
        if doc.solicitud_id != solicitud_id:
            raise ValueError("el documento no pertenece a la solicitud")
        resultado = decision["resultado"]
        if resultado == "OBSERVADO":
            motivo = decision.get("motivo", "").strip()
            if not motivo:
                raise ValueError("motivo obligatorio al observar")
            doc.estado = "OBSERVADO"
            db.add(Observacion(auditoria_id=audit.id, documento_id=doc.id,
                               motivo=motivo))
            nombre = db.get(TipoDocumento, doc.tipo_documento_id).nombre
            observados.append({"documento_id": doc.id, "nombre": nombre,
                               "motivo": motivo})
        elif resultado == "APROBADO":
            doc.estado = "APROBADO"
            for obs in db.query(Observacion).filter_by(
                    documento_id=doc.id, resuelta_en=None).all():
                from datetime import datetime
                obs.resuelta_en = datetime.utcnow()
        else:
            raise ValueError(f"resultado inválido: {resultado}")
    if observados:
        audit.resultado = "OBSERVADO"
        registrar_transicion(db, sol, "OBSERVADA", f"auditor:{auditor_id}")
        registrar_transicion(db, sol, "PENDIENTE_ALUMNO", f"auditor:{auditor_id}")
        evento, datos = "OBSERVADA", {"observaciones": observados}
    else:
        registrar_transicion(db, sol, "DOCUMENTACION_APROBADA", f"auditor:{auditor_id}")
        evento, datos = "DOCUMENTACION_APROBADA", {"numero": sol.numero}
    db.commit()
    if on_event is not None:
        on_event(evento, datos)
    return audit
```

`backend/app/auditorias/router.py`:
```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.auditorias.models import Auditoria, Observacion
from app.auditorias.service import registrar_auditoria
from app.auth.models import Usuario
from app.documentos.models import Documento, DocumentoVersion
from app.infra.db import get_db
from app.notificaciones.events import publicar_evento
from app.solicitudes.models import Solicitud

router = APIRouter(prefix="/auditorias", tags=["auditorias"])

class Decision(BaseModel):
    documento_id: int
    resultado: str
    motivo: str | None = None

class AuditoriaIn(BaseModel):
    auditor_id: int
    decisiones: list[Decision]

@router.get("/solicitudes")
def listar(estado: str | None = None, carrera_id: int | None = None,
           db: Session = Depends(get_db)):
    query = db.query(Solicitud)
    if estado:
        query = query.filter_by(estado=estado)
    if carrera_id:
        query = query.filter_by(carrera_id=carrera_id)
    return query.all()

@router.get("/solicitudes/{solicitud_id}/documentos")
def documentos(solicitud_id: int, db: Session = Depends(get_db)):
    filas = (db.query(Documento, DocumentoVersion)
             .outerjoin(DocumentoVersion,
                        Documento.version_vigente_id == DocumentoVersion.id)
             .filter(Documento.solicitud_id == solicitud_id).all())
    return [{"documento_id": doc.id, "estado": doc.estado,
             "object_key": version.object_key if version else None,
             "observaciones": [o.motivo for o in db.query(Observacion).filter_by(
                 documento_id=doc.id, resuelta_en=None).all()]}
            for doc, version in filas]

@router.post("/solicitudes/{solicitud_id}")
def auditar(solicitud_id: int, data: AuditoriaIn, db: Session = Depends(get_db)):
    auditor = db.get(Usuario, data.auditor_id)
    if auditor is None or not auditor.activo or auditor.rol not in ("auditor", "admin"):
        raise HTTPException(403, "auditor no autorizado")
    try:
        return registrar_auditoria(
            db, solicitud_id, data.auditor_id,
            [d.model_dump() for d in data.decisiones],
            on_event=lambda evento, datos: publicar_evento(
                db, solicitud_id, evento, datos,
                on_enqueue=lambda nid: None))
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_auditorias.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add backend && git commit -m "feat: add document audit and observations"
```

---

### Task 10: Subsanación con conservación de versiones

**Files:**
- Create: `backend/tests/test_subsanacion.py`
- Modify: `backend/app/solicitudes/router.py`, `backend/app/documentos/router.py`

**Interfaces:**
- Consumes: `registrar_documento`, `registrar_transicion`, `Observacion`.
- Produces: `GET /solicitudes/{id}/documentos-observados`; reemplazo vía `POST /documentos/upload-url` seguido de `POST /solicitudes/{id}/reenviar`.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_subsanacion.py`:
```python
import hashlib
from sqlalchemy.orm import Session
from app.alumnos.models import Alumno
from app.auditorias.models import Auditoria, Observacion
from app.catalogos.models import Carrera, Convocatoria, TipoDocumento
from app.documentos.models import Documento, DocumentoVersion
from app.documentos.service import registrar_documento
from app.solicitudes.models import Solicitud
from app.solicitudes.service import registrar_transicion

class FakeStore:
    def put_bytes(self, key, data): pass
    def get_bytes(self, key): return b""
    def exists(self, key): return True
    def presigned_put(self, key, ct, expires): return f"http://minio/{key}"
    def presigned_get(self, key, expires): return f"http://minio/{key}"


def test_reemplazo_conserva_versiones(db: Session):
    conv = Convocatoria(nombre="2026-sub", anio=2026, activa=True)
    car = Carrera(nombre="Economía", codigo="ECOSUB", activa=True)
    alumno = Alumno(apellido="Gómez", nombres="Pedro", dni="33123456",
                    email="pedro-sub@example.com", celular="+5493815555555")
    td = TipoDocumento(codigo="dni", nombre="DNI", tamano_maximo_bytes=10485760)
    db.add_all([conv, car, alumno, td])
    db.flush()
    sol = Solicitud(numero="FACE-2026-90003", alumno_id=alumno.id,
                    convocatoria_id=conv.id, carrera_id=car.id,
                    tipo_ingresante="nuevo", dni=alumno.dni, estado="PENDIENTE_ALUMNO")
    db.add(sol)
    db.flush()
    doc = Documento(solicitud_id=sol.id, tipo_documento_id=td.id, estado="OBSERVADO")
    db.add(doc)
    db.flush()
    db.add(DocumentoVersion(documento_id=doc.id, numero=1, object_key="s/1/dni/v1.pdf",
                            mime="application/pdf", bytes=3, checksum="old",
                            creado_por="alumno"))
    audit = Auditoria(solicitud_id=sol.id, auditor_id=1, resultado="OBSERVADO")
    db.add(audit)
    db.flush()
    db.add(Observacion(auditoria_id=audit.id, documento_id=doc.id,
                       motivo="Imagen ilegible"))
    db.commit()

    data = b"new"
    registrar_documento(db, sol.id, td.id, "dni.pdf", "application/pdf", len(data),
                        hashlib.sha256(data).hexdigest(), "pedro-sub@example.com",
                        FakeStore())
    registrar_transicion(db, sol, "REENVIADA", "alumno")
    registrar_transicion(db, sol, "EN_REAUDITORIA", "worker")
    assert db.query(DocumentoVersion).filter_by(documento_id=doc.id).count() == 2
    assert db.get(Documento, doc.id).estado == "REEMPLAZADO"
    assert sol.estado == "EN_REAUDITORIA"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_subsanacion.py -v`
Expected: FAIL por ausencia del endpoint `/reenviar` (y del test de integración del flujo).

- [ ] **Step 3: Write minimal implementation**

Agregar a `backend/app/solicitudes/router.py`:
```python
class ReenviarIn(BaseModel):
    version: int

@router.get("/solicitudes/{solicitud_id}/documentos-observados")
def documentos_observados(solicitud_id: int, db: Session = Depends(get_db)):
    filas = (db.query(Observacion, Documento)
             .join(Documento, Observacion.documento_id == Documento.id)
             .filter(Documento.solicitud_id == solicitud_id,
                     Observacion.resuelta_en.is_(None)).all())
    return [{"documento_id": doc.id, "tipo_documento_id": doc.tipo_documento_id,
             "motivo": obs.motivo} for obs, doc in filas]

@router.post("/solicitudes/{solicitud_id}/reenviar")
def reenviar(solicitud_id: int, payload: ReenviarIn, db: Session = Depends(get_db)):
    sol = db.get(Solicitud, solicitud_id)
    if sol is None:
        raise HTTPException(404, "solicitud no encontrada")
    if sol.version != payload.version:
        raise HTTPException(409, "versión obsoleta")
    from worker.tasks import validar_documentos_solicitud
    registrar_transicion(db, sol, "REENVIADA", "alumno")
    db.add(Notificacion(
        solicitud_id=solicitud_id, evento="REENVIADA", canal="email",
        destinatario="auditores@face.unt.edu.ar", estado="PENDIENTE",
        idempotency_key=f"reenviada|{solicitud_id}|{sol.version}"))
    db.commit()
    validar_documentos_solicitud.delay(solicitud_id)
    from worker.tasks import enviar_notificacion
    enviar_notificacion.delay(db.query(Notificacion).filter_by(
        idempotency_key=f"reenviada|{solicitud_id}|{sol.version}").one().id)
    return {"estado": sol.estado}
```
En `backend/app/documentos/router.py`, `POST /documentos/upload-url` ya reutiliza `registrar_documento`, por lo que un documento `OBSERVADO` pasa a `REEMPLAZADO` y crea la versión 2 sin borrar la anterior. El import de `Notificacion` se agrega al router.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_subsanacion.py -v`
Expected: PASS (1 test).

- [ ] **Step 5: Commit**

```bash
git add backend && git commit -m "feat: add document replacement and resubmission"
```

---

### Task 11: Notificaciones por correo y WhatsApp simulado

**Files:**
- Create: `backend/app/notificaciones/templates.py`, `backend/app/notificaciones/events.py`, `backend/app/notificaciones/service.py`, `backend/app/notificaciones/router.py`, `backend/app/infra/whatsapp.py`, `backend/tests/test_notificaciones.py`
- Modify: `backend/app/auditorias/router.py`, `backend/app/main.py`

**Interfaces:**
- Consumes: `Notificacion`, `Consentimiento`, `Alumno`, `EmailSender`.
- Produces: `publicar_evento(db, solicitud_id, evento, datos, on_enqueue=None) -> list[int]`, `enviar_notificacion(notificacion_id, sender, whatsapp, db) -> Notificacion`, `WhatsAppMock.send(to, body) -> None`.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_notificaciones.py`:
```python
from sqlalchemy.orm import Session
from app.alumnos.models import Alumno
from app.catalogos.models import Carrera, Convocatoria
from app.notificaciones.events import publicar_evento
from app.notificaciones.models import Consentimiento, Notificacion
from app.notificaciones.service import enviar_notificacion
from app.notificaciones.templates import plantilla_observaciones
from app.solicitudes.models import Solicitud

class FakeSender:
    def __init__(self): self.enviados = []
    def send(self, to, subject, body): self.enviados.append((to, subject, body))

class FakeWhatsApp:
    def __init__(self): self.enviados = []
    def send(self, to, body): self.enviados.append((to, body))

def test_publicacion_y_envio(db: Session):
    conv = Convocatoria(nombre="2026-not", anio=2026, activa=True)
    car = Carrera(nombre="Economía", codigo="ECONOT", activa=True)
    alumno = Alumno(apellido="Pérez", nombres="Ana", dni="30123456",
                    email="ana-not@example.com", celular="+5493815555555")
    db.add_all([conv, car, alumno])
    db.flush()
    sol = Solicitud(numero="FACE-2026-90004", alumno_id=alumno.id,
                    convocatoria_id=conv.id, carrera_id=car.id,
                    tipo_ingresante="nuevo", dni=alumno.dni, estado="PENDIENTE_ALUMNO")
    db.add(sol)
    db.flush()
    db.add(Consentimiento(alumno_id=alumno.id, canal="whatsapp", aceptado=True))
    db.commit()
    encolados = []
    ids = publicar_evento(db, sol.id, "OBSERVADA",
                          {"observaciones": [{"documento_id": 7,
                                               "motivo": "DNI ilegible"}]},
                          on_enqueue=encolados.append)
    assert len(ids) == 2 and len(encolados) == 2
    assert {db.get(Notificacion, i).canal for i in ids} == {"email", "whatsapp"}
    email, wa = FakeSender(), FakeWhatsApp()
    for i in ids:
        enviar_notificacion(i, email, wa, db)
    assert len(email.enviados) == 1 and len(wa.enviados) == 1
    assert "DNI ilegible" in email.enviados[0][2]
    assert all(db.get(Notificacion, i).estado == "ENVIADA" for i in ids)

def test_idempotencia(db: Session):
    conv = Convocatoria(nombre="2026-idem", anio=2026, activa=True)
    car = Carrera(nombre="Economía", codigo="ECOIDEM", activa=True)
    alumno = Alumno(apellido="Gómez", nombres="Ana", dni="34123456",
                    email="ana-idem@example.com", celular="+5493815555555")
    db.add_all([conv, car, alumno])
    db.flush()
    sol = Solicitud(numero="FACE-2026-90007", alumno_id=alumno.id,
                    convocatoria_id=conv.id, carrera_id=car.id,
                    tipo_ingresante="nuevo", dni=alumno.dni, estado="PENDIENTE_ALUMNO")
    db.add(sol)
    db.commit()
    datos = {"observaciones": [{"documento_id": 7, "motivo": "x"}]}
    ids1 = publicar_evento(db, sol.id, "OBSERVADA", datos)
    ids2 = publicar_evento(db, sol.id, "OBSERVADA", datos)
    assert ids1 == ids2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_notificaciones.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'app.notificaciones.events'`.

- [ ] **Step 3: Write minimal implementation**

`backend/app/notificaciones/templates.py`:
```python
URL_PORTAL = "https://inscripciones.face.unt.edu.ar"

def plantilla_observaciones(nombre: str, numero: str,
                            observaciones: list[dict]) -> tuple[str, str]:
    items = "\n".join(f"{i}. {o.get('nombre', o['documento_id'])}: {o['motivo']}"
                      for i, o in enumerate(observaciones, 1))
    asunto = "Observaciones en su documentación – Preinscripción FACE"
    cuerpo = (f"Estimado/a {nombre}:\n\nDurante la revisión de su documentación "
              f"correspondiente a la preinscripción en FACE se detectaron las "
              f"siguientes observaciones:\n{items}\n\nPara subsanarlas ingrese a "
              f"{URL_PORTAL}.\nSolicitud: {numero}.\n\nDepartamento de Alumnos – FACE")
    return asunto, cuerpo

def plantilla_aprobada(nombre: str, numero: str) -> tuple[str, str]:
    asunto = "Documentación aprobada – Preinscripción FACE"
    cuerpo = (f"Estimado/a {nombre}:\n\nSu documentación de la solicitud {numero} "
              f"fue aprobada. Puede continuar el trámite administrativo en {URL_PORTAL}.\n\n"
              f"Departamento de Alumnos – FACE")
    return asunto, cuerpo
```

`backend/app/notificaciones/events.py`:
```python
import hashlib
import json
from sqlalchemy.orm import Session
from app.alumnos.models import Alumno
from app.notificaciones.models import Consentimiento, Notificacion
from app.notificaciones.templates import plantilla_observaciones, plantilla_aprobada
from app.solicitudes.models import Solicitud

def publicar_evento(db: Session, solicitud_id: int, evento: str,
                    datos: dict, on_enqueue=None) -> list[int]:
    sol = db.get(Solicitud, solicitud_id)
    alumno = db.get(Alumno, sol.alumno_id) if sol else None
    nombre = alumno.nombres if alumno else "estudiante"
    numero = sol.numero if sol else str(solicitud_id)
    if evento == "OBSERVADA":
        asunto, cuerpo = plantilla_observaciones(nombre, numero, datos["observaciones"])
    else:
        asunto, cuerpo = plantilla_aprobada(nombre, numero)
    canales = ["email"]
    if alumno and db.query(Consentimiento).filter_by(
            alumno_id=alumno.id, canal="whatsapp", aceptado=True).first():
        canales.append("whatsapp")
    ids = []
    for canal in canales:
        payload = json.dumps({"evento": evento, "asunto": asunto, "cuerpo": cuerpo},
                             sort_keys=True)
        key = hashlib.sha256(f"{evento}|{canal}|{payload}".encode()).hexdigest()[:64]
        row = db.query(Notificacion).filter_by(idempotency_key=key).one_or_none()
        if row is None:
            row = Notificacion(solicitud_id=solicitud_id, evento=evento, canal=canal,
                               destinatario=alumno.email if alumno else "desconocido@face",
                               estado="PENDIENTE", asunto=asunto, cuerpo=cuerpo,
                               idempotency_key=key)
            db.add(row)
            db.commit()
        ids.append(row.id)
        if on_enqueue is not None:
            on_enqueue(row.id)
    return ids
```

`backend/app/notificaciones/service.py`:
```python
from datetime import datetime
from sqlalchemy.orm import Session
from app.notificaciones.models import Notificacion

def enviar_notificacion(notificacion_id: int, sender, whatsapp, db: Session) -> Notificacion:
    row = db.get(Notificacion, notificacion_id)
    if row.estado == "ENVIADA":
        return row
    try:
        if row.canal == "email":
            sender.send(row.destinatario, row.asunto, row.cuerpo)
        else:
            whatsapp.send(row.destinatario, row.cuerpo)
        row.estado = "ENVIADA"
        row.error = None
    except Exception as exc:
        row.intentos += 1
        row.estado = "FALLIDA"
        row.error = str(exc)
        raise
    finally:
        db.commit()
    return row
```

`backend/app/infra/whatsapp.py`:
```python
import json
from pathlib import Path
from datetime import datetime

class WhatsAppMock:
    def __init__(self, path: str = "var/whatsapp-mock.log"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
    def send(self, to: str, body: str) -> None:
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"fecha": datetime.utcnow().isoformat(),
                                 "para": to, "cuerpo": body}, ensure_ascii=False) + "\n")
```

`backend/app/notificaciones/router.py`:
```python
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.infra.db import get_db
from app.notificaciones.models import Consentimiento

router = APIRouter(prefix="/alumnos", tags=["consentimientos"])

class ConsentimientoIn(BaseModel):
    alumno_id: int
    canal: str
    aceptado: bool

@router.post("/{alumno_id}/consentimientos")
def registrar(alumno_id: int, data: ConsentimientoIn, db: Session = Depends(get_db)):
    fila = Consentimiento(alumno_id=alumno_id, canal=data.canal,
                          aceptado=data.aceptado)
    db.add(fila)
    db.commit()
    return {"alumno_id": alumno_id, "canal": data.canal, "aceptado": data.aceptado}
```

En `backend/app/auditorias/router.py`, el handler de auditoría pasa:
```python
on_event=lambda evento, datos: publicar_evento(
    db, solicitud_id, evento, datos,
    on_enqueue=lambda nid: enviar_notificacion.delay(nid))
```
(importando `enviar_notificacion` de `worker.tasks`).

Agregar a `backend/worker/tasks.py`:
```python
from app.infra.config import get_settings
from app.infra.email import EmailSender
from app.infra.whatsapp import WhatsAppMock
from app.notificaciones.service import enviar_notificacion as _enviar

@celery_app.task(name="notificaciones.enviar", bind=True, max_retries=5)
def enviar_notificacion(self, notificacion_id: int):
    with SessionLocal() as db:
        try:
            _enviar(notificacion_id, EmailSender(get_settings()),
                    WhatsAppMock(), db)
        except Exception as exc:
            row = db.get(Notificacion, notificacion_id)
            raise self.retry(exc=exc, countdown=60 * (row.intentos + 1))
```
(con `SessionLocal` de `app.infra.db` y `Notificacion` de `app.notificaciones.models` importados arriba).

En `backend/app/main.py`, registrar los routers que antes no estaban disponibles:
```python
from app.auditorias.router import router as auditorias_router
from app.notificaciones.router import router as consentimientos_router
app.include_router(auditorias_router)
app.include_router(consentimientos_router)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_notificaciones.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add backend && git commit -m "feat: add email and mocked WhatsApp notifications"
```

---

### Task 12: Tablero de indicadores

**Files:**
- Create: `backend/app/reportes/router.py`, `backend/tests/test_reportes.py`
- Modify: `backend/app/main.py`

**Interfaces:**
- Consumes: `Solicitud`, `Observacion`, `Notificacion`, `Documento`.
- Produces: `GET /reportes/resumen` y `GET /reportes/observaciones-por-documento`.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_reportes.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_reportes.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'app.reportes'`.

- [ ] **Step 3: Write minimal implementation**

`backend/app/reportes/router.py`:
```python
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.documentos.models import Documento
from app.infra.db import get_db
from app.notificaciones.models import Notificacion
from app.solicitudes.models import Solicitud

router = APIRouter(prefix="/reportes", tags=["reportes"])

@router.get("/resumen")
def resumen(db: Session = Depends(get_db)):
    filas = db.query(Solicitud.estado, func.count(Solicitud.id)).group_by(Solicitud.estado).all()
    por_estado = {estado: total for estado, total in filas}
    return {
        "total": sum(por_estado.values()),
        "por_estado": por_estado,
        "notificaciones_enviadas": db.query(Notificacion).filter_by(estado="ENVIADA").count(),
        "notificaciones_fallidas": db.query(Notificacion).filter_by(estado="FALLIDA").count(),
    }

@router.get("/observaciones-por-documento")
def observaciones_por_documento(db: Session = Depends(get_db)):
    filas = (db.query(Documento.tipo_documento_id, func.count(Documento.id))
             .filter(Documento.estado == "OBSERVADO")
             .group_by(Documento.tipo_documento_id).all())
    return [{"tipo_documento_id": tipo, "cantidad": n} for tipo, n in filas]

admin_router = APIRouter(prefix="/admin", tags=["admin"])

class CierreIn(BaseModel):
    actor: str
    motivo: str | None = None

@admin_router.post("/solicitudes/{solicitud_id}/finalizar")
def finalizar(solicitud_id: int, data: CierreIn, db: Session = Depends(get_db)):
    sol = db.get(Solicitud, solicitud_id)
    if sol is None:
        raise HTTPException(404, "solicitud no encontrada")
    try:
        registrar_transicion(db, sol, "FINALIZADA", data.actor, data.motivo)
    except InvalidTransition as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"estado": sol.estado}

@admin_router.post("/solicitudes/{solicitud_id}/rechazar")
def rechazar(solicitud_id: int, data: CierreIn, db: Session = Depends(get_db)):
    sol = db.get(Solicitud, solicitud_id)
    if sol is None:
        raise HTTPException(404, "solicitud no encontrada")
    if not data.motivo:
        raise HTTPException(422, "motivo obligatorio para rechazar")
    registrar_transicion(db, sol, "RECHAZADA", data.actor, data.motivo)
    return {"estado": sol.estado}
```
(con `BaseModel` de pydantic, `HTTPException` de fastapi, `registrar_transicion` de `app.solicitudes.service` e `InvalidTransition` de `app.solicitudes.state`).

`backend/app/main.py`: registrar ambos routers:
```python
from app.reportes.router import router as reportes_router, admin_router
app.include_router(reportes_router)
app.include_router(admin_router)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_reportes.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add backend && git commit -m "feat: add management dashboard endpoints"
```

---

### Task 13: Portal Angular del alumno

**Files:**
- Create: proyecto Angular en `frontend/` (`ng new frontend --standalone --routing --style=scss --skip-git --defaults`), `frontend/src/app/core/api.service.ts`, `frontend/src/app/portal/solicitud.service.ts`, `frontend/src/app/portal/datos-personales/datos-personales.component.ts`, `frontend/src/app/portal/datos-personales/datos-personales.component.spec.ts`, `frontend/src/app/portal/documentos/documentos.component.ts`, `frontend/src/app/portal/seguimiento/seguimiento.component.ts`, `frontend/src/app/app.routes.ts` (modificar), `frontend/src/environments/environment.ts`

**Interfaces:**
- Consumes: API endpoints de Tasks 5-10.
- Produces: servicios `ApiService`, `SolicitudService`; rutas `/portal/datos`, `/portal/documentos`, `/portal/seguimiento`.

- [ ] **Step 1: Write the failing test**

`frontend/src/app/portal/datos-personales/datos-personales.component.spec.ts`:
```typescript
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { DatosPersonalesComponent } from './datos-personales.component';

describe('DatosPersonalesComponent', () => {
  let fixture: ComponentFixture<DatosPersonalesComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [DatosPersonalesComponent],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    fixture = TestBed.createComponent(DatosPersonalesComponent);
    fixture.detectChanges();
  });

  it('el formulario empieza inválido y se habilita con los datos obligatorios', () => {
    const component = fixture.componentInstance;
    expect(component.form.valid).toBeFalse();
    component.form.setValue({
      apellido: 'Pérez', nombres: 'Ana', dni: '30123456',
      email: 'ana@example.com', celular: '+5493815555555',
      convocatoria_id: 1, carrera_id: 1, tipo_ingresante: 'nuevo',
    });
    expect(component.form.valid).toBeTrue();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- --watch=false --browsers=ChromeHeadless`
Expected: FAIL porque el componente no existe.

- [ ] **Step 3: Write minimal implementation**

`frontend/src/environments/environment.ts`:
```typescript
export const environment = { apiUrl: 'http://localhost:8000' };
```

`frontend/src/app/core/api.service.ts`:
```typescript
import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { environment } from '../../environments/environment';

@Injectable({ providedIn: 'root' })
export class ApiService {
  private http = inject(HttpClient);
  private base = environment.apiUrl;

  get<T>(path: string, params?: Record<string, string | number>) {
    let query = new HttpParams();
    if (params) Object.entries(params).forEach(([k, v]) => query = query.set(k, v));
    return this.http.get<T>(`${this.base}${path}`, { params: query });
  }

  post<T>(path: string, body: unknown) {
    return this.http.post<T>(`${this.base}${path}`, body);
  }
}
```

`frontend/src/app/portal/solicitud.service.ts`:
```typescript
import { Injectable, inject } from '@angular/core';
import { ApiService } from '../core/api.service';

export interface Solicitud {
  id: number;
  numero: string | null;
  estado: string;
}

@Injectable({ providedIn: 'root' })
export class SolicitudService {
  private api = inject(ApiService);

  crear(data: Record<string, unknown>) {
    return this.api.post<Solicitud>('/solicitudes', data);
  }

  obtener(id: number) {
    return this.api.get<Solicitud>(`/solicitudes/${id}`);
  }

  confirmar(id: number, version: number) {
    return this.api.post<Solicitud>(`/solicitudes/${id}/confirmar`, { version });
  }

  observados(id: number) {
    return this.api.get<{ documento_id: number; motivo: string }[]>(
      `/solicitudes/${id}/documentos-observados`);
  }

  reenviar(id: number, version: number) {
    return this.api.post<Solicitud>(`/solicitudes/${id}/reenviar`, { version });
  }

  pedirUrlSubida(body: Record<string, unknown>) {
    return this.api.post<{ url: string; documento_id: number; expires_in: number }>(
      '/documentos/upload-url', body);
  }
}
```

`frontend/src/app/portal/datos-personales/datos-personales.component.ts`:
```typescript
import { Component, inject } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { SolicitudService } from '../solicitud.service';

@Component({
  selector: 'app-datos-personales',
  standalone: true,
  imports: [ReactiveFormsModule],
  template: `
    <form [formGroup]="form" (ngSubmit)="guardar()">
      <label>Apellido <input formControlName="apellido"></label>
      <label>Nombres <input formControlName="nombres"></label>
      <label>DNI <input formControlName="dni"></label>
      <label>Correo <input formControlName="email" type="email"></label>
      <label>Celular <input formControlName="celular"></label>
      <button type="submit" [disabled]="form.invalid">Guardar borrador</button>
    </form>
  `,
})
export class DatosPersonalesComponent {
  private fb = inject(FormBuilder);
  private service = inject(SolicitudService);
  form = this.fb.nonNullable.group({
    apellido: ['', Validators.required],
    nombres: ['', Validators.required],
    dni: ['', Validators.required],
    email: ['', [Validators.required, Validators.email]],
    celular: ['', Validators.required],
    convocatoria_id: [1, Validators.required],
    carrera_id: [1, Validators.required],
    tipo_ingresante: ['nuevo', Validators.required],
  });
  guardar() {
    if (this.form.valid) {
      this.service.crear(this.form.getRawValue()).subscribe(sol => {
        localStorage.setItem('solicitudId', String(sol.id));
      });
    }
  }
}
```

`frontend/src/app/portal/documentos/documentos.component.ts`:
```typescript
import { Component, inject } from '@angular/core';
import { Router } from '@angular/router';
import { SolicitudService } from '../solicitud.service';
import { sha256 } from './checksum';

const REQUISITOS = [
  { id: 1, codigo: 'dni', nombre: 'DNI (frente y dorso)' },
  { id: 2, codigo: 'foto_carnet', nombre: 'Foto carnet' },
  { id: 3, codigo: 'acta_nacimiento', nombre: 'Acta de nacimiento' },
  { id: 4, codigo: 'titulo_secundario', nombre: 'Título secundario' },
  { id: 5, codigo: 'formulario_siu', nombre: 'Formulario SIU Guaraní' },
  { id: 6, codigo: 'comprobante_pago', nombre: 'Comprobante de pago' },
];

@Component({
  selector: 'app-documentos',
  standalone: true,
  template: `
    <h1>Documentación requerida</h1>
    @for (req of requisitos; track req.id) {
      <section>
        <h2>{{ req.nombre }}</h2>
        <input type="file" accept=".pdf,.jpg,.jpeg,.png"
               (change)="subir(req.id, $event)">
      </section>
    } @empty { <p>Sin requisitos</p> }
  `,
})
export class DocumentosComponent {
  private service = inject(SolicitudService);
  private router = inject(Router);
  requisitos = REQUISITOS;
  solicitudId = Number(localStorage.getItem('solicitudId') ?? 0);

  async subir(tipoDocumentoId: number, event: Event) {
    const archivo = (event.target as HTMLInputElement).files?.[0];
    if (!archivo) return;
    const checksum = await sha256(archivo);
    this.service.pedirUrlSubida({
      solicitud_id: this.solicitudId,
      tipo_documento_id: tipoDocumentoId,
      filename: archivo.name,
      content_type: archivo.type,
      size: archivo.size,
      checksum,
    }).subscribe(({ url }) => {
      fetch(url, { method: 'PUT', body: archivo,
                   headers: { 'Content-Type': archivo.type } });
    });
  }
}
```
`frontend/src/app/portal/documentos/checksum.ts`:
```typescript
export async function sha256(archivo: File): Promise<string> {
  const buffer = await archivo.arrayBuffer();
  const hash = await crypto.subtle.digest('SHA-256', buffer);
  return Array.from(new Uint8Array(hash))
    .map(b => b.toString(16).padStart(2, '0')).join('');
}
```
(el componente importa `sha256` desde `./checksum`).

`frontend/src/app/portal/seguimiento/seguimiento.component.ts`:
```typescript
import { Component, OnInit, inject } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { SolicitudService } from '../solicitud.service';

@Component({
  selector: 'app-seguimiento',
  standalone: true,
  template: `
    <h1>Mi preinscripción</h1>
    <p>Solicitud: {{ numero }}</p>
    <p>Estado: {{ estado }}</p>
    @for (obs of observados; track obs.documento_id) {
      <article>Documento {{ obs.documento_id }}: {{ obs.motivo }}</article>
    }
    <button (click)="corregir()">Corregir documentos</button>
  `,
})
export class SeguimientoComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private service = inject(SolicitudService);
  numero = '';
  estado = '';
  observados: { documento_id: number; motivo: string }[] = [];
  id = Number(this.route.snapshot.paramMap.get('id'));

  ngOnInit() {
    this.service.obtener(this.id).subscribe(sol => {
      this.numero = sol.numero ?? 'Borrador';
      this.estado = sol.estado;
    });
    this.service.observados(this.id).subscribe(items => this.observados = items);
  }

  corregir() {
    this.router.navigate(['/portal/documentos']);
  }
}
```

`frontend/src/app/app.routes.ts`:
```typescript
import { Routes } from '@angular/router';
export const routes: Routes = [
  { path: 'portal/datos', loadComponent: () =>
      import('./portal/datos-personales/datos-personales.component')
        .then(m => m.DatosPersonalesComponent) },
  { path: 'portal/documentos', loadComponent: () =>
      import('./portal/documentos/documentos.component')
        .then(m => m.DocumentosComponent) },
  { path: 'portal/seguimiento/:id', loadComponent: () =>
      import('./portal/seguimiento/seguimiento.component')
        .then(m => m.SeguimientoComponent) },
  { path: '', pathMatch: 'full', redirectTo: 'portal/datos' },
];
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm test -- --watch=false --browsers=ChromeHeadless`
Expected: PASS (1 test).

- [ ] **Step 5: Commit**

```bash
git add frontend && git commit -m "feat: add student portal with document upload"
```

---

### Task 14: Panel de auditoría, administración y arranque completo

**Files:**
- Create: `frontend/src/app/auditoria/panel/panel.component.ts`, `frontend/src/app/auditoria/panel/panel.component.spec.ts`, `frontend/src/app/admin/dashboard/dashboard.component.ts`, `backend/Dockerfile`, `frontend/Dockerfile`, `frontend/nginx.conf`
- Modify: `frontend/src/app/app.routes.ts`, `infra/docker-compose.yml`, `backend/README.md`
- Create: `scripts/e2e.sh`

**Interfaces:**
- Consumes: endpoints `/auditorias`, `/reportes`, `/catalogos`.
- Produces: rutas `/auditoria`, `/admin`; `docker compose up` levanta los siete servicios.

- [ ] **Step 1: Write the failing test**

`frontend/src/app/auditoria/panel/panel.component.spec.ts`:
```typescript
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { PanelComponent } from './panel.component';

describe('PanelComponent', () => {
  let fixture: ComponentFixture<PanelComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [PanelComponent],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    fixture = TestBed.createComponent(PanelComponent);
    fixture.detectChanges();
  });

  it('muestra el estado vacío hasta cargar solicitudes', () => {
    expect(fixture.nativeElement.textContent).toContain('Sin solicitudes');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- --watch=false --browsers=ChromeHeadless`
Expected: FAIL porque `PanelComponent` no existe.

- [ ] **Step 3: Write minimal implementation**

`frontend/src/app/auditoria/panel/panel.component.ts`:
```typescript
import { Component, OnInit, inject } from '@angular/core';
import { ApiService } from '../../core/api.service';

interface Fila {
  id: number;
  numero: string;
  dni: string;
  carrera: string;
  estado: string;
}

@Component({
  selector: 'app-panel',
  standalone: true,
  template: `
    <h1>Auditoría documental</h1>
    @for (fila of filas; track fila.numero) {
      <article>
        <strong>{{ fila.numero }}</strong> — {{ fila.dni }} — {{ fila.estado }}
        <button (click)="auditar(fila)">Auditar</button>
      </article>
    } @empty {
      <p>Sin solicitudes</p>
    }
  `,
})
export class PanelComponent implements OnInit {
  private api = inject(ApiService);
  filas: Fila[] = [];

  ngOnInit() {
    this.api.get<Fila[]>('/auditorias/solicitudes?estado=EN_AUDITORIA')
      .subscribe(filas => this.filas = filas);
  }

  auditar(fila: Fila) {
    this.api.post(`/auditorias/solicitudes/${fila.id}`, {
      auditor_id: 1,
      decisiones: [{ documento_id: 1, resultado: 'APROBADO' }],
    }).subscribe();
  }
}
```

`frontend/src/app/admin/dashboard/dashboard.component.ts`:
```typescript
import { Component, OnInit, inject } from '@angular/core';
import { ApiService } from '../../core/api.service';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  template: `
    <h1>Tablero FACE</h1>
    <p>Total: {{ resumen.total }}</p>
    <p>Correos enviados: {{ resumen.notificaciones_enviadas }}</p>
    <p>Correos fallidos: {{ resumen.notificaciones_fallidas }}</p>
  `,
})
export class DashboardComponent implements OnInit {
  private api = inject(ApiService);
  resumen = { total: 0, notificaciones_enviadas: 0, notificaciones_fallidas: 0,
              por_estado: {} as Record<string, number> };
  ngOnInit() {
    this.api.get<typeof this.resumen>('/reportes/resumen')
      .subscribe(data => this.resumen = data);
  }
}
```

Agregar a `frontend/src/app/app.routes.ts`:
```typescript
  { path: 'auditoria', loadComponent: () =>
      import('./auditoria/panel/panel.component').then(m => m.PanelComponent) },
  { path: 'admin', loadComponent: () =>
      import('./admin/dashboard/dashboard.component').then(m => m.DashboardComponent) },
```

`backend/Dockerfile`:
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e .
COPY app worker alembic.ini ./
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

`frontend/Dockerfile`:
```dockerfile
FROM node:22-alpine AS build
WORKDIR /src
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build
FROM nginx:1.27-alpine
COPY --from=build /src/dist/frontend/browser /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

`frontend/nginx.conf` redirige rutas SPA a `/index.html` y hace proxy de `/api` a `http://api:8000`.

Agregar a `infra/docker-compose.yml`:
```yaml
  api:
    build: ../backend
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000
    env_file: .env
    ports: ["8000:8000"]
    depends_on: [postgres, minio, redis, mailpit]
  worker:
    build: ../backend
    command: celery -A app.infra.celery_app:celery_app worker --loglevel=info
    env_file: .env
    depends_on: [postgres, minio, redis, mailpit]
  frontend:
    build: ../frontend
    ports: ["4200:80"]
    depends_on: [api]
```

`scripts/e2e.sh` (verificación manual automatizada del circuito):
```bash
#!/usr/bin/env bash
set -euo pipefail
BASE=http://localhost:8000
curl -fsS "$BASE/health"
curl -fsS -X POST "$BASE/auth/request-otp" -H 'Content-Type: application/json' \
  -d '{"email":"ana@example.com"}'
echo "Ver el OTP en http://localhost:8025 y luego:"
echo "POST /auth/verify-otp, POST /solicitudes, POST /documentos/upload-url, POST /solicitudes/{id}/confirmar"
echo "Revisar la solicitud en el panel /auditoria y los correos en Mailpit."
```

`backend/README.md` incorpora la sección "Producción": HTTPS obligatorio con Traefik, backups programados de PostgreSQL y MinIO, antivirus antes de aceptar archivos, política de conservación/eliminación definida por FACE, acceso restringido a discapacidad y cumplimiento de la Ley 25.326. El WhatsApp simulado se reemplaza por WhatsApp Business Cloud API sin cambiar `publicar_evento`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm test -- --watch=false --browsers=ChromeHeadless`
Luego: `docker compose -f infra/docker-compose.yml up -d --build` y `bash scripts/e2e.sh`.
Expected: PASS (1 test de Angular); los siete servicios responden y el circuito puede recorrerse desde el portal y el panel.

- [ ] **Step 5: Commit**

```bash
git add frontend backend infra scripts && git commit -m "feat: add audit panel, dashboard and full local stack"
```



