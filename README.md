# FACE — Sistema de preinscripción y auditoría documental

Sistema local/self-hosted para la **preinscripción** de ingresantes y la **auditoría documental** de la Facultad de Ciencias Económicas (FACE) – UNT. Cubre el circuito completo: datos del aspirante, carga de documentos, validación automática, auditoría humana, observaciones, subsanación, reauditoría, notificaciones y reportes.

> Estado actual: implementación funcional en rama `implementacion`, verificada localmente y desplegada en Dokploy. Antes de producción faltan confirmaciones de negocio, hardening de seguridad/operación y configuración SMTP real (ver [Lo que falta](#lo-que-falta)).

## Alcance

**Incluye**
- Portal de preinscripción: datos personales, carrera, tipo de ingresante, borrador y confirmación.
- Generación de número `FACE-AAAA-NNNNN` al confirmar la solicitud.
- Carga documental con validación de MIME (`application/pdf`, `image/jpeg`, `image/png`), tamaño máximo `10485760` bytes (10 MB), SHA-256 y versionado.
- URLs prefirmadas MinIO: subida 900 s, descarga 300 s.
- Validación automática por worker (Celery/Redis) y decisión final humana por auditor.
- Observaciones documentadas, subsanación por el alumno y reauditoría.
- Notificaciones por correo e idempotencia; WhatsApp simulado (sin integración real).
- Panel de auditoría, dashboard administrativo y reportes.
- Acceso alumno por OTP de correo (sin cuenta institucional).

**Fuera de alcance**
- Inscripción administrativa definitiva.
- Integración SIU Guaraní.
- OCR/IA sobre documentos.
- WhatsApp Business Cloud API real.
- Borrado automático de documentos.

## Stack

| Capa | Tecnología |
|---|---|
| Frontend | Angular 20, TypeScript, Nginx |
| Backend | FastAPI, SQLAlchemy, Alembic, Pydantic |
| Workers | Celery + Redis |
| Base de datos | PostgreSQL 16 |
| Objetos | MinIO (S3 compatible) |
| Correo local/dev | Mailpit |
| Correo productivo | SMTP configurable (Gmail/SMTP institucional; preparado en código) |
| Infra local | Docker Compose |
| Despliegue | Dokploy + Traefik + red `dokploy-network` |

## Estructura del repositorio

```text
.
├── backend/                  # FastAPI, modelos, servicios, migraciones, tests
├── frontend/                 # Angular 20
├── infra/                    # docker-compose local, .env.example, scripts
├── worker/                   # tareas Celery (validación/notificaciones)
├── docs/superpowers/         # spec y plan aprobados
├── docker-compose.dokploy.yml# compose para despliegue en Dokploy
└── README.md
```

Documentos de referencia:
- Spec: `docs/superpowers/specs/2026-11-24-sistema-preinscripciones-face-design.md`
- Plan: `docs/superpowers/plans/2026-11-24-sistema-preinscripciones-face.md`

## Ejecución local

### 1) Requisitos

- Docker / Docker Compose
- Python 3.12+ (recomendado usar `backend/.venv`)
- Node 20+

### 2) Infraestructura

```bash
docker compose -f infra/docker-compose.yml up -d
```

Servicios locales típicos: PostgreSQL, PostgreSQL de test, MinIO, Redis, Mailpit, API, worker y frontend (según compose).

### 3) Backend

```bash
cd backend
python -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/pytest -q
```

> Usar siempre `backend/.venv/bin/pytest` para correr tests del backend.

### 4) Frontend

```bash
cd frontend
npm ci
npm run build
CHROME_BIN=/tmp/opencode/chrome-headless-nosandbox npm test -- --watch=false --browsers=ChromeHeadless
```

### 5) Credenciales demo locales

| Email | Rol | Password |
|---|---|---|
| `auditor@face.unt.edu.ar` | auditor | `auditor-local` |
| `admin@face.unt.edu.ar` | admin | `admin-local` |

**No usar en producción.** Deben rotarse/eliminarse antes de exponer el sistema.

## Variables de entorno

Base: `infra/.env.example`.

| Variable | Descripción | Ejemplo/local |
|---|---|---|
| `DATABASE_URL` | BD principal | `postgresql+psycopg://face:face@localhost:5432/face` |
| `TEST_DATABASE_URL` | BD de tests | `postgresql+psycopg://face:face@localhost:5433/face_test` |
| `MINIO_ENDPOINT` | Endpoint interno MinIO | `minio:9000` / `localhost:9000` |
| `MINIO_PUBLIC_ENDPOINT` | Endpoint público para URLs prefirmadas | `localhost:9000` o dominio público |
| `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` | Credenciales MinIO | secret |
| `MINIO_BUCKET` | Bucket de documentos | `face-documentos` |
| `REDIS_URL` | Redis/Celery | `redis://localhost:6379/0` |
| `SMTP_HOST` / `SMTP_PORT` | SMTP | Mailpit local: `localhost:1025` |
| `SMTP_USER` / `SMTP_PASSWORD` | Auth SMTP (Gmail/App Password) | vacío en local |
| `SMTP_FROM` | Remitente | `preinscripcion@face.unt.edu.ar` |
| `SMTP_TLS` / `SMTP_SSL` | Seguridad SMTP | Gmail: `TLS=true`, `SSL=false` |
| `SECRET_KEY` | Secreto JWT/app | valor largo aleatorio |
| `OTP_TTL_SECONDS` | Vigencia OTP | `600` |
| `OTP_MAX_INTENTOS` | Intentos OTP | `5` |
| `UPLOAD_URL_TTL` | Presigned PUT | `900` |
| `DOWNLOAD_URL_TTL` | Presigned GET | `300` |
| `CORS_ORIGINS` | Orígenes permitidos API | `https://dominio-frontend` |
| `SEED_DEMO` | Carga catálogos/usuarios demo al iniciar | `true` en demo, `false` en producción |
| `EXPOSE_DOCS` | Publica `/docs` y `/openapi.json` | `false` en producción |

## Despliegue en Dokploy

El despliegue actual usa `docker-compose.dokploy.yml` como compose de la app en Dokploy, reutilizando servicios existentes en `dokploy-network`.

### Servicios FACE

- `api`: FastAPI + migraciones Alembic al iniciar.
- `worker`: Celery.
- `frontend`: Angular compilado servido por Nginx.

### Recursos externos reutilizados (dedicados a FACE)

- PostgreSQL existente en Dokploy: BD `face_preinscripciones`, usuario dedicado.
- MinIO existente en Dokploy: bucket `face-preinscripciones`, usuario/policy dedicados.
- Redis existente en Dokploy: DB dedicada para Celery.
- Traefik/Dokploy para dominios y TLS.

### Dominios actuales (sslip.io)

- Frontend: `http://face-6bf2d3-200-58-102-223.sslip.io/`
- API: `http://face-api-6bf2d3-200-58-102-223.sslip.io/health`
- Mailpit público: deshabilitado en Dokploy (se recomienda no exponerlo).

> En Dokploy se activó HTTPS/Let’s Encrypt para frontend y API. La emisión efectiva depende de que el dominio público resuelva correctamente y Let’s Encrypt pueda validar el challenge. Para `sslip.io` puede requerir ajuste DNS/certificado según el entorno.

### SMTP / correo real

Mailpit era solo para desarrollo local. Para correo real el backend soporta SMTP con login, STARTTLS o SSL implícito:

1. Obtener credenciales SMTP del proveedor (Gmail requiere **App Password** con 2FA).
2. Cargar en el entorno del compose de Dokploy:
   ```env
   # Puerto 587 (STARTTLS)
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USER=cuenta@gmail.com
   SMTP_PASSWORD=app-password
   SMTP_FROM=cuenta@gmail.com
   SMTP_TLS=true
   SMTP_SSL=false
   ```
   Para **puerto 465** usar SSL implícito: `SMTP_SSL=true` y `SMTP_TLS=false`.
3. Redeployar el compose y probar `POST /auth/request-otp`.

> Verificado en el deploy actual: el proveedor configurado usa puerto 465 con `SMTP_SSL=true`; el OTP respondió `202` y la notificación de aprobación quedó `ENVIADA`.

No commitear credenciales SMTP. Cargarlas solo en el Environment de Dokploy o en un archivo local con `chmod 600` fuera del repo.

### Gestión de usuarios admin/auditor

La imagen de la API incluye una CLI para crear/rotar usuarios sin tocar seeds:

```bash
# Listar
docker exec face-preinscripciones-6bf2d3-fhxt9q-api-1 python -m app.auth.cli listar

# Crear (lee la contraseña de stdin, mínimo 10 caracteres)
docker exec -i face-preinscripciones-6bf2d3-fhxt9q-api-1 \
  python -m app.auth.cli crear --email auditora@face.unt.edu.ar --rol auditor --password-stdin

# Cambiar contraseña / reactivar
docker exec -i face-preinscripciones-6bf2d3-fhxt9q-api-1 \
  python -m app.auth.cli password --email auditora@face.unt.edu.ar --password-stdin

# Desactivar un usuario demo
docker exec face-preinscripciones-6bf2d3-fhxt9q-api-1 \
  python -m app.auth.cli desactivar --email auditor@face.unt.edu.ar
```

Para producción: crear las cuentas reales, verificar acceso y recién entonces desactivar las demo y/o poner `SEED_DEMO=false`.

## Verificación

Comandos usados en el proyecto:

```bash
# Backend
cd backend && .venv/bin/pytest -q

# Frontend
cd frontend && CHROME_BIN=/tmp/opencode/chrome-headless-nosandbox npm test -- --watch=false --browsers=ChromeHeadless
cd frontend && npm run build

# Compose
docker compose -f infra/docker-compose.yml config --quiet
```

Resultado de verificación reciente: backend **47 passed**, `npm run build` OK, compose config OK y E2E completo ejecutado contra el deploy de Dokploy (alta de solicitud, carga de documentos, validación, auditoría y notificación enviada).

## Lo que falta

### Estado verificado (2026-11-25)

- Backend: **47 passed** (`pytest -q`), incluyendo pruebas de autorización API.
- Frontend: `npm run build` OK.
- E2E sobre el deploy Dokploy: OTP alumno → borrador → 6 documentos a MinIO → confirmación (`FACE-2026-00001`) → validación worker → auditoría completa → `DOCUMENTACION_APROBADA` → notificación `ENVIADA`.
- Auth: alumno por OTP; admin/auditor por JWT. El backend deriva la identidad del auditor desde el token y ya no confía en `auditor_id` enviado por el cliente.
- SMTP real verificado: `POST /auth/request-otp` respondió `202` y la notificación de aprobación quedó `ENVIADA`.

### Bloqueantes antes de producción (requieren acción humana/FACE)

- [ ] **Confirmaciones de negocio FACE (spec §7)**: carreras, tipos de ingresante, requisitos por convocatoria, importes y fechas reales, política de conservación documental y número de WhatsApp habilitado.
- [ ] **Rotar secretos expuestos en chat**: token de GitHub y API key de Dokploy deben revocarse/rotarse en sus consolas.
- [ ] **Credenciales demo**: crear cuentas reales con la CLI, verificar acceso y luego desactivar `auditor@face.unt.edu.ar` / `admin@face.unt.edu.ar` (o `SEED_DEMO=false`).
- [ ] **Dominios y HTTPS definitivos**: reemplazar `sslip.io` por dominios institucionales FACE, configurar DNS y validar Let’s Encrypt + redirección HTTP→HTTPS.
- [ ] **Backups con restauración probada**: PostgreSQL y MinIO (ver `docs/OPERACION_PRODUCCION.md`).
- [ ] **Monitoreo y alertas**: API, worker Celery, cola, SMTP, MinIO, PostgreSQL, disco y logs centralizados.
- [ ] **Antivirus y retención**: escaneo de archivos y política de conservación/borrado (Ley 25.326 para datos sensibles/discapacidad).

### Operación y seguridad

- [x] Headers de seguridad, HSTS en HTTPS y rate limit básico en endpoints de auth.
- [x] Docs OpenAPI deshabilitables (`EXPOSE_DOCS=false`).
- [x] Seed demo deshabilitable (`SEED_DEMO=false`).
- [x] Autorización por rol/ownership en solicitudes, documentos, auditoría y reportes.
- [x] CLI de usuarios admin/auditor.
- [ ] Rate limiting distribuido en Traefik/WAF si se escala a más de una instancia (el actual es en memoria por proceso).
- [ ] Gestión de secretos en gestor dedicado; revisar historial/logs de despliegue por tokens embebidos.

### Funcional/producto

- [ ] **WhatsApp real**: reemplazar simulación por WhatsApp Business Cloud API, manteniendo evento/idempotencia.
- [ ] **Integración SIU Guaraní**: fuera del MVP actual; definir contrato y alcance.
- [ ] **OCR/IA**: no implementado por decisión de alcance.
- [ ] **Datos seed definitivos**: reemplazar carreras/tipos/requisitos demo por los oficiales de FACE.
- [ ] **UX/E2E de navegador**: probar manualmente en el navegador sobre el dominio final (OTP alumno, auditor, admin, subsanación y expiración de token).

Ver runbook operativo: `docs/OPERACION_PRODUCCION.md`.

## Seguridad

- No pegar tokens, API keys o contraseñas en issues, chats o commits.
- Rotar inmediatamente cualquier secreto expuesto.
- Usar App Password de Gmail; no contraseña principal.
- No exponer Mailpit en producción.
- Limitar acceso a reportes/admin por rol y red.

## Licencia / propiedad

Uso interno FACE/UNT. Definir licencia y política de distribución antes de publicar el repositorio.