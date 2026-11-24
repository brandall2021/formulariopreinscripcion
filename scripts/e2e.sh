#!/usr/bin/env bash
set -euo pipefail
if [ ! -f infra/.env ]; then cp infra/.env.example infra/.env; fi
BASE=http://localhost:8000
curl -fsS "$BASE/health"
curl -fsS -X POST "$BASE/auth/request-otp" -H 'Content-Type: application/json' \
  -d '{"email":"ana@example.com"}'
echo "Ver el OTP en http://localhost:8025 y luego:"
echo "POST /auth/verify-otp, POST /solicitudes, POST /documentos/upload-url, POST /solicitudes/{id}/confirmar"
echo "Revisar la solicitud en el panel /auditoria y los correos en Mailpit."
