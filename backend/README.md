# FACE Preinscripción — backend

## Desarrollo local

Levantar la infraestructura (PostgreSQL 16 en 5432 y BD de pruebas en 5433, MinIO, Redis y Mailpit):

```bash
docker compose -f infra/docker-compose.yml up -d
```

Instalar dependencias y ejecutar tests:

```bash
cd backend && pip install -e '.[dev]'
pytest -v
```

Usuarios semilla para demo local (no usar en producción):

| Email | Rol | Password |
| --- | --- | --- |
| `auditor@face.unt.edu.ar` | auditor | `auditor-local` |
| `admin@face.unt.edu.ar` | admin | `admin-local` |

## Producción

- HTTPS obligatorio, terminado en Traefik.
- Backups programados de PostgreSQL y MinIO.
- Antivirus antes de aceptar archivos.
- Política de conservación/eliminación de documentos definida por FACE.
- Acceso restringido a los datos de discapacidad y cumplimiento de la Ley 25.326.
- El WhatsApp simulado se reemplaza por WhatsApp Business Cloud API sin cambiar `publicar_evento`.
