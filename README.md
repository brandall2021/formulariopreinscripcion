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

### SMTP / Gmail

Mailpit era solo para desarrollo local. Para correo real:

1. Crear una **App Password** de Gmail (cuenta con 2FA).
2. Cargar en el entorno del compose de Dokploy:
   ```env
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USER=cuenta@gmail.com
   SMTP_PASSWORD=app-password
   SMTP_FROM=cuenta@gmail.com
   SMTP_TLS=true
   SMTP_SSL=false
   ```
3. Redeployar el compose.

No commitear credenciales SMTP. El archivo `/tmp/opencode/smtp.env` puede usarse localmente en el servidor con `chmod 600`, pero no debe versionarse.

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

Resultado de verificación reciente del circuito completo (antes de los cambios locales pendientes de commit): backend 43 passed, frontend 5 SUCCESS + build OK, compose config OK, E2E real con solicitud finalizada y notificaciones enviadas.

## Lo que falta

### Bloqueantes antes de producción

- [ ] **Confirmaciones de negocio FACE (spec §7)**: lista oficial de carreras, tipos de ingresante, requisitos por convocatoria, importes y fechas reales, política de conservación documental, número de WhatsApp habilitado.
- [ ] **SMTP real/Gmail**: cargar credenciales App Password en Dokploy y validar envío real de OTP/notificaciones.
- [ ] **Rotar secretos expuestos en chat**: token de GitHub y API key de Dokploy compartidos durante la sesión deben rotarse/revocarse.
- [ ] **Credenciales demo**: cambiar/eliminar `auditor@face.unt.edu.ar` y `admin@face.unt.edu.ar` o deshabilitarlas fuera de demo.
- [ ] **HTTPS efectivo en dominios públicos definitivos**: validar emisión Let’s Encrypt y redirección HTTP→HTTPS en los dominios finales de FACE.
- [ ] **Autorización completa en frontend**: integrar login OTP/admin, almacenamiento de token, interceptor `Authorization: Bearer` y guards por rol. El backend ya tiene hardening parcial en trabajo local; sin frontend adaptado, endpoints protegidos romperían la UI actual.
- [ ] **Autorización JWT/roles end-to-end**: revisar todos los endpoints sensibles, ownership por solicitud/documento y casos de auditor/admin/alumno; agregar pruebas de autorización.
- [ ] **Revisión de exposición**: Mailpit no debe quedar público; endpoints administrativos/reportes solo para roles autorizados.

### Operación y seguridad

- [ ] **Backups**: programar backups de PostgreSQL y MinIO; probar restauración.
- [ ] **Monitoreo y alertas**: logs centralizados, healthchecks, alertas por worker caído, cola atrasada, errores SMTP/MinIO/DB.
- [ ] **Antivirus**: escaneo de archivos antes de aceptarlos/entregarlos en producción.
- [ ] **Política de conservación**: definir retención/borrado documental; la entrega actual no borra automáticamente.
- [ ] **Gestión de secretos**: mover secretos a gestor/variables seguras de Dokploy; no usar `.env` con secretos en git.
- [ ] **Hardening de despliegue**: revisar headers, rate limiting, CORS final, TLS, tamaños máximos, timeouts, límites de carga.
- [ ] **Datos sensibles**: revisar acceso a datos de discapacidad y cumplimiento Ley 25.326.
- [ ] **Limpieza de config Dokploy**: eliminar token embebido en historial/logs de despliegue si quedó registrado; usar credencial Git de Dokploy/SSH.

### Funcional/producto

- [ ] **WhatsApp real**: reemplazar simulación por WhatsApp Business Cloud API, manteniendo el evento/idempotencia.
- [ ] **Integración SIU Guaraní**: fuera del MVP actual; definir contrato y alcance.
- [ ] **OCR/IA**: no implementado por decisión de alcance.
- [ ] **Datos seed definitivos**: reemplazar carreras/tipos/requisitos de demo por los oficiales de FACE.
- [ ] **UX de auth**: pantallas de ingreso OTP para alumno y login admin/auditor; manejo de expiración de token.
- [ ] **Auditoría/observabilidad de negocio**: métricas y trazabilidad operativa para mesa de ayuda.

### Cambios locales pendientes de commit/deploy

Hay cambios en el worktree que aún no fueron commiteados ni desplegados en Dokploy:

- Hardening parcial de auth JWT/roles en backend.
- Soporte SMTP configurable para Gmail (`SMTP_USER/PASSWORD/FROM/TLS/SSL`).
- `docker-compose.dokploy.yml` preparado para Gmail y sin Mailpit.

Antes de desplegarlos, validar compatibilidad con el frontend actual o implementar primero la autenticación del frontend.

## Seguridad

- No pegar tokens, API keys o contraseñas en issues, chats o commits.
- Rotar inmediatamente cualquier secreto expuesto.
- Usar App Password de Gmail; no contraseña principal.
- No exponer Mailpit en producción.
- Limitar acceso a reportes/admin por rol y red.

## Licencia / propiedad

Uso interno FACE/UNT. Definir licencia y política de distribución antes de publicar el repositorio.