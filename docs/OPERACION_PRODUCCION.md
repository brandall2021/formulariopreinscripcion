# Operación y producción — FACE Preinscripción

Este documento resume lo que falta para pasar de demo a producción y los pasos operativos.

## 1. Bloqueantes externos (requieren acción humana/FACE)

- **SMTP real**: configurar en Dokploy Environment del compose `face-preinscripciones-6bf2d3-fhxt9q`:
  - `SMTP_HOST=smtp.gmail.com`
  - `SMTP_PORT=587`
  - `SMTP_USER=<cuenta>`
  - `SMTP_PASSWORD=<app-password>`
  - `SMTP_FROM=<cuenta>`
  - `SMTP_TLS=true`
  - `SMTP_SSL=false`
  Luego redeploy y probar OTP/notificación.
- **Rotar secretos expuestos**: revocar/rotar token GitHub y API key Dokploy que fueron compartidos en chat; revisar logs de deploy.
- **Credenciales demo**: desactivar/cambiar usuarios seed `auditor@face.unt.edu.ar` y `admin@face.unt.edu.ar` o poner `SEED_DEMO=false` y crear usuarios productivos seguros. Para crear/rotar usuarios usar la CLI incluida en la imagen de la API:
  ```bash
  docker exec -i face-preinscripciones-6bf2d3-fhxt9q-api-1 \
    python -m app.auth.cli crear --email auditora@face.unt.edu.ar --rol auditor --password-stdin
  docker exec face-preinscripciones-6bf2d3-fhxt9q-api-1 \
    python -m app.auth.cli desactivar --email auditor@face.unt.edu.ar
  ```
  Crear y verificar las cuentas reales **antes** de desactivar las demo para no perder acceso.
- **Dominios oficiales FACE**: reemplazar `sslip.io` por dominios institucionales, configurar DNS, habilitar Let’s Encrypt/Traefik y forzar HTTPS.
- **Datos oficiales FACE §7**: carreras, tipos de ingresante, requisitos por convocatoria, importes/fechas reales, política de conservación, número WhatsApp habilitado.

## 2. Hardening ya implementado en código

- CORS configurable por `CORS_ORIGINS`.
- Headers de seguridad básicos: `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, HSTS en HTTPS.
- Rate limit en memoria para `/auth/request-otp`, `/auth/verify-otp`, `/auth/admin/login` (si se escala a más de una instancia, complementar en Traefik/WAF).
- El backend deriva la identidad del auditor del token JWT; ignora `auditor_id` enviado por el cliente.
- `/documentos/{version_id}/validar` exige rol auditor/admin.
- Docs OpenAPI deshabilitables con `EXPOSE_DOCS=false`.
- Seed demo deshabilitable con `SEED_DEMO=false`.
- SMTP configurable con TLS/SSL/login para Gmail/SMTP institucional.

## 3. Backups (ejecutar y automatizar)

### PostgreSQL

```bash
# Backup
docker exec <postgres-container> pg_dump -U <user> -Fc <db> > /backups/face_$(date +%F_%H%M).dump

# Restore (prueba periódica)
docker exec -i <postgres-container> pg_restore -U <user> -d <db> --clean --if-exists < /backups/face_YYYY-MM-DD_HHMM.dump
```

### MinIO

Usar `mc mirror` o versión/replicación del bucket. Probar restauración de un objeto y verificación de checksum.

### Política
- Retención diaria/semanal/mensual definida por FACE.
- Cifrado en reposo del almacenamiento de backups.
- Prueba de restauración al menos mensual.

## 4. Monitoreo y alertas

- Healthchecks: `/health` (liveness), `/health/ready` (PostgreSQL + Redis + MinIO, responde 503 si algo falla), estado del worker Celery y cola.
- Alertas: 5xx API, worker sin heartbeat, cola atrasada, fallos SMTP, fallos MinIO, disco.
- Logs centralizados y retención definida.

## 5. Seguridad y cumplimiento

- Antivirus/scan de archivos antes de aceptación definitiva o antes de descarga interna según política.
- Ley 25.326: minimizar datos, controlar acceso a discapacidad, auditoría de accesos, política de privacidad.
- Rate limiting externo en Traefik/WAF además del límite en app.
- Revisar dependencias y parches.

## 6. Checklist antes de abrir a usuarios reales

- [ ] SMTP real probado con OTP y notificación.
- [ ] Secretos rotados y fuera de git/chat.
- [ ] `SEED_DEMO=false` en producción y usuarios reales creados.
- [ ] Dominios oficiales + HTTPS válido.
- [ ] Backups automáticos + restore probado.
- [ ] Monitoreo/alertas activos.
- [ ] Antivirus/retención definidos.
- [ ] Catálogos/datos §7 oficiales cargados.
- [ ] E2E en navegador sobre dominio final.