# Diseño: Sistema de preinscripción y auditoría documental FACE (UNT)

- Fecha: 2026-11-24
- Estado: diseño aprobado por el usuario; pendiente de revisión del documento escrito
- Fuente funcional: [Diseño funcional de la aplicación de preinscripción e inscripción de alumnos.pdf](https://github.com/brandall2021/opencod/blob/main/Dise%C3%B1o%20funcional%20de%20la%20aplicaci%C3%B3n%20de%20preinscripci%C3%B3n%20e%20inscripci%C3%B3n%20de%20alumnos.pdf)

## 1. Contexto y objetivo

La FACE (UNT) necesita reemplazar el formulario estático de preinscripción por un sistema web que gestione el circuito documental completo: recepción, validación automática, auditoría humana, observaciones, subsanación por parte del alumno y notificaciones. El valor central es la trazabilidad: cada archivo tiene versiones, cada evaluación tiene un auditor y fecha, cada observación apunta a un documento concreto y cada cambio de estado queda registrado.

Objetivo de esta entrega: **preinscripción + auditoría** funcionando de punta a punta en un entorno local con PostgreSQL y MinIO.

Fuera de alcance de esta entrega: trámite administrativo de inscripción, integración con SIU Guaraní, OCR/IA en producción, WhatsApp Business real y despliegue institucional. Quedan documentados como evoluciones posteriores.

## 2. Decisiones confirmadas

| Decisión | Valor |
| --- | --- |
| Alcance | Preinscripción + auditoría (incluye subsanación y notificaciones) |
| Auditoría | Validación automática de archivos y requisitos; decisión final humana |
| Stack | Angular + FastAPI + workers Python, PostgreSQL y MinIO locales |
| Orquestación local | Docker Compose; Redis para cola y Celery como worker |
| Correo | SMTP local con Mailpit |
| WhatsApp | Proveedor simulado que registra mensajes, estados e intentos |
| Acceso del alumno | Sin cuenta institucional: registro con correo y OTP por correo |
| Organización | Monorepo con entregas verticales de circuito completo |
| Ubicación | `/root/preinscripciones-face` |

El documento de referencia especifica PDF, JPG y PNG, 10 MB por archivo y datos personales: apellido, nombres, DNI, fecha de nacimiento, correo verificado, celular con código de país, carrera, domicilio y declaración de discapacidad. Los requisitos se configuran por convocatoria, carrera y tipo de ingresante. No se trasladan a FACE importes, fechas ni requisitos propios de FACET.

## 3. Arquitectura

### 3.1 Servicios Docker Compose

| Servicio | Función | Persistencia |
| --- | --- | --- |
| `postgres` | PostgreSQL 16, datos y auditoría | volumen `pgdata` |
| `minio` | Almacenamiento privado de documentos y versiones | volumen `miniodata` |
| `redis` | Broker y resultados de Celery | sin persistencia crítica |
| `mailpit` | SMTP local y bandeja de correos de prueba | en memoria |
| `api` | FastAPI, reglas de negocio y API REST | — |
| `worker` | Celery: validación, notificaciones, reintentos | — |
| `frontend` | Angular (dev server en local; build estático en producción) | — |

Traefik se documenta para despliegue pero no se incluye en el Compose local. La API expone el OpenAPI y el frontend consume solo HTTP; el navegador nunca recibe credenciales de MinIO.

### 3.2 Estructura del repositorio

```
backend/
  app/
    auth/            # OTP, sesiones, dependencias de roles
    alumnos/         # datos personales y consentimientos
    catalogos/       # convocatorias, carreras, tipos de documento, requisitos
    solicitudes/     # ciclo de vida y máquina de estados
    documentos/      # upload prefirmado, versiones, validación
    auditorias/      # decisiones y observaciones
    notificaciones/  # eventos, plantillas, registro de envíos
    reportes/        # indicadores del tablero
    infra/           # sqlalchemy, migraciones, clientes MinIO/Redis/SMTP
  tests/
frontend/
  src/app/
    portal/          # registro, datos, carga, seguimiento, corrección
    auditoria/       # cola, visor, decisión
    admin/           # convocatorias, roles, tablero
worker/
  celery_app.py
  tasks/
infra/
  docker-compose.yml
  .env.example
docs/
  superpowers/specs/
```

### 3.3 Límites de responsabilidad

- La **API** es la única que escribe estado en PostgreSQL y decide permisos. Emitir una URL prefirmada no cambia el estado del documento.
- El **worker** consume tareas: validación de archivos, generación y envío de notificaciones, reintentos. Nunca aprueba documentos.
- El **frontend** no accede a MinIO directamente: pide a la API una URL de subida o de visualización con caducidad corta.
- Los **proveedores externos** reciben solo datos de la notificación, nunca los archivos.

## 4. Modelo de datos PostgreSQL

### 4.1 Tablas

| Tabla | Contenido principal |
| --- | --- |
| `alumnos` | apellido, nombres, dni, fecha_nacimiento, email, celular (código de país), domicilio, discapacidad |
| `usuarios` | personal administrativo: email, hash de contraseña, rol (`auditor`, `admin`), activo |
| `convocatorias` | nombre, año, fecha_apertura, fecha_cierre, activa |
| `carreras` | nombre, código, activa |
| `tipos_documentos` | código, nombre, descripción, formatos permitidos, tamaño máximo |
| `requisitos_documentales` | convocatoria + carrera + tipo_ingresante + tipo_documento + obligatorio |
| `solicitudes` | número, alumno, convocatoria, carrera, tipo_ingresante, estado, timestamps, versión optimista |
| `documentos` | solicitud, tipo_documento, estado, versión vigente |
| `documento_versiones` | documento, número de versión, object_key de MinIO, mime, bytes, checksum, creado_por, creado_en |
| `auditorias` | solicitud, auditor, resultado, fecha, observaciones generales |
| `observaciones` | auditoría, documento, motivo, resuelta_en |
| `notificaciones` | solicitud, evento, canal (`email`/`whatsapp`), destinatario, estado, intentos, error, idempotency_key |
| `consentimientos` | alumno, canal, aceptado, fecha |
| `historial_estados` | solicitud, estado_anterior, estado_nuevo, actor, fecha, motivo |
| `otp_codigos` | email, hash del código, expiración, intentos, usado_en |

### 4.2 Reglas de integridad

- Índice único `(convocatoria_id, dni)` sobre `solicitudes`: un DNI no puede generar dos solicitudes para la misma convocatoria.
- `numero_solicitud` con formato `FACE-AAAA-NNNNN`, generado de forma atómica al confirmar la presentación.
- Un `documentos` referencia su versión vigente; cada reemplazo inserta una nueva `documento_versiones` y deja la anterior intacta en MinIO y en la tabla.
- Toda `observaciones` referencia un `documentos.id`; no existen observaciones generales sin documento.
- Toda transición de `solicitudes.estado` inserta un registro en `historial_estados`.
- Control optimista mediante `updated_at`/versión en `solicitudes` y `documentos`: una decisión basada en una versión obsoleta responde `409`.

### 4.3 Máquina de estados de la solicitud

Transiciones permitidas:

```
BORRADOR → RECIBIDA
RECIBIDA → EN_VALIDACION
EN_VALIDACION → EN_AUDITORIA
EN_AUDITORIA → DOCUMENTACION_APROBADA
EN_AUDITORIA → OBSERVADA
OBSERVADA → PENDIENTE_ALUMNO
PENDIENTE_ALUMNO → REENVIADA
REENVIADA → EN_REAUDITORIA
EN_REAUDITORIA → DOCUMENTACION_APROBADA
EN_REAUDITORIA → OBSERVADA
DOCUMENTACION_APROBADA → FINALIZADA
Cualquier estado activo → RECHAZADA (solo administración, con motivo)
```

`DOCUMENTACION_APROBADA` significa que la documentación está aprobada; **no** implica que el alumno esté inscripto en SIU Guaraní. `FINALIZADA` y `RECHAZADA` son decisiones administrativas.

### 4.4 Estados de documento

`PENDIENTE` (sin archivo), `RECIBIDO`, `EN_REVISION`, `APROBADO`, `OBSERVADO`, `REEMPLAZADO`. Al cargar una nueva versión de un documento observado, el estado pasa a `REEMPLAZADO` y queda pendiente de reauditoría; la observación anterior se marca resuelta recién cuando el auditor aprueba la versión nueva.

## 5. Flujos funcionales

### 5.1 Registro y presentación del alumno

1. El alumno ingresa su correo; la API envía un OTP por correo (Mailpit en local).
2. Valida el OTP y obtiene una sesión con token.
3. Completa datos personales, selecciona convocatoria/carrera/tipo de ingresante y registra de forma explícita su consentimiento opcional para recibir WhatsApp.
4. Guarda un borrador y puede volver después.
5. Solicita URLs prefirmadas para subir cada documento; el navegador sube directamente a MinIO.
6. Confirma la presentación. La API valida que todos los requisitos obligatorios estén presentes, que el mime sea `application/pdf`, `image/jpeg` o `image/png`, que el tamaño no exceda el configurado, y que el checksum coincida.
7. Genera número de solicitud, comprobante de recepción, fecha/hora y estado `RECIBIDA`; encola la validación automática.

### 5.2 Validación automática y auditoría

1. El worker verifica integridad del archivo y lo marca `RECIBIDO`/`EN_REVISION`; la solicitud pasa a `EN_AUDITORIA`.
2. El auditor ve una cola filtrable por estado, carrera y fecha. Abre un documento, lo visualiza o descarga con URL temporizada.
3. Decide `APROBADO` u `OBSERVADO`. Si observa, debe indicar motivo obligatorio y se crea una observación asociada al documento.
4. Se registran auditor, fecha y versión del documento evaluado. La decisión no la toma el worker.

### 5.3 Subsanación

1. El alumno ve exclusivamente sus documentos observados con el motivo del auditor.
2. Reemplaza cada archivo: se crea nueva versión, se conserva la anterior y se genera una URL de visualización nueva.
3. La solicitud pasa a `REENVIADA` → `EN_REAUDITORIA`; se notifica al auditor.
4. Si aprueba todas las versiones nuevas, la solicitud pasa a `DOCUMENTACION_APROBADA` y las observaciones se cierran.

### 5.4 Notificaciones

- La transición a `OBSERVADA` publica un evento con la lista de documentos observados y sus motivos.
- La transición a `DOCUMENTACION_APROBADA` publica un evento de confirmación.
- El worker envía correo y WhatsApp simulado como tareas independientes; cada canal registra resultado, intentos y error.
- Reintentos con backoff acotado e `idempotency_key` compuesta por evento + canal + documento. Si falla WhatsApp, el correo ya enviado no se reenvía.
- WhatsApp respeta `consentimientos`: si el alumno no aceptó ese canal, no se encola mensaje y se registra el motivo.
- Plantillas: asunto `Observaciones en su documentación – Preinscripción FACE`, cuerpo con la lista numerada de observaciones, enlace al portal y número de solicitud; versión aprobada con texto de confirmación.

### 5.5 Superficies de API

Grupos: `/auth`, `/alumnos`, `/convocatorias`, `/solicitudes`, `/documentos`, `/auditorias`, `/notificaciones`, `/reportes`, `/admin`.

Códigos: `400`/`422` para validación, `401`/`403` para autenticación y roles, `404` para recursos inexistentes, `409` para transiciones inválidas o versión obsoleta. Formato de error único con `code`, `message` y `details`.

## 6. Seguridad y privacidad

- Bucket MinIO privado, sin enlaces públicos; URLs prefirmadas con caducidad de minutos y ámbito de una sola operación.
- Roles `alumno`, `auditor` y `admin`; el alumno solo ve sus propias solicitudes y documentos.
- Registro de auditoría de descargas, reemplazos y decisiones.
- HTTPS obligatorio en producción; en local se documenta el proxy futuro.
- Copias de seguridad de PostgreSQL y MinIO; antivirus en producción (opcional en local) antes de aceptar un archivo.
- Declaración de discapacidad con acceso restringido a roles autorizados.
- La política de conservación y eliminación documental es responsabilidad de FACE; esta entrega no implementa borrado automático y conserva todas las versiones.
- Cumplimiento de la Ley 25.326: minimalismo de datos, consentimiento registrado y acceso controlado.
- Los mensajeros externos reciben solo el resultado de auditoría, nunca documentos completos.

## 7. Datos de ejemplo y confirmaciones externas

Se cargan como semilla: convocatoria 2026 de ejemplo, carreras `Contador Público`, `Economía` y `Administración` (tomadas de los ejemplos del PDF), seis tipos de documento (DNI frente/dorso, foto carnet, acta de nacimiento, título secundario, formulario SIU Guaraní y comprobante de pago) y requisitos obligatorios configurados para esa convocatoria.

Antes de producción, FACE debe confirmar: lista oficial de carreras, tipos de ingresante, requisitos por convocatoria, importes y fechas reales, política de conservación documental y número de WhatsApp habilitado. Estos datos no bloquean la implementación local porque son configuración, no lógica.

## 8. Pruebas y criterios de aceptación

- `pytest`: máquina de estados, reglas de requisitos, observaciones por documento, permisos, idempotencia y reintentos del worker.
- Integración contra PostgreSQL y MinIO del Compose: subida, versionado y URLs caducadas.
- Angular: pruebas unitarias de formularios y componentes críticos; recorrido extremo a extremo manual o automatizado del circuito completo.
- Criterio de aceptación de cada entrega vertical: un alumno puede presentar, un auditor puede observar, el alumno puede corregir y el estado final es correcto, con trazabilidad en `historial_estados` y notificaciones registradas.

## 9. Entregas verticales

1. **Infra + acceso + catálogos + solicitud:** Compose, migraciones, OTP por correo, roles, convocatorias/carreras/tipos de documento, borrador y confirmación con número de solicitud.
2. **Documentos y validación:** MinIO privado, URLs prefirmadas, carga PDF/JPG/PNG, límite de tamaño, checksum, versiones y worker de validación.
3. **Auditoría y subsanación:** panel, visor, aprobación/observación con motivo, versiones, observaciones resueltas y transiciones `REENVIADA`/`EN_REAUDITORIA`.
4. **Notificaciones y cierre:** eventos, Mailpit, WhatsApp simulado, reintentos, consentimientos, tablero de indicadores y endurecimiento de seguridad.

Cada entrega deja el circuito funcionando de extremo a extremo; no se construyen módulos aislados que luego deban conectarse.
