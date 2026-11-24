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
