# FACE Frontend Design Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mejorar integralmente la experiencia Angular de FACE para alumno,
auditor y administrador sin romper el contrato API existente.

**Architecture:** Crear una capa visual global y componentes standalone pequeños,
manteniendo `ApiService`, auth y rutas. Cada pantalla manejará explícitamente
loading, error, éxito y estado vacío; las acciones de negocio seguirán usando
los endpoints actuales.

**Tech Stack:** Angular 20, standalone components, Reactive Forms, SCSS, CSS
native, Vitest/Karma existente.

**Spec:** `docs/superpowers/specs/2026-11-25-face-frontend-design.md`

## Global Constraints

- MIME permitido: `application/pdf`, `image/jpeg`, `image/png`.
- Tamaño máximo: `10485760` bytes.
- Mantener rutas y contratos backend existentes.
- No usar `window.prompt` para decisiones de auditoría.
- No agregar librería UI pesada.

---

### Task 1: Sistema visual y shell de navegación

**Files:**
- Modify: `frontend/src/styles.scss`
- Create: `frontend/src/app/shared/app-shell.component.ts`
- Modify: `frontend/src/app/app.routes.ts`

- [ ] Definir variables CSS para color, spacing, radios, sombras, foco y
  estados.
- [ ] Crear shell con encabezado, marca FACE, navegación contextual, usuario y
  botón de salida.
- [ ] Aplicar layout responsive y `main` con landmark accesible.
- [ ] Envolver rutas autenticadas con el shell sin cambiar guards.
- [ ] Ejecutar `npm run build`.
- [ ] Commit: `feat: add FACE visual shell and responsive design`.

### Task 2: Estado común de UI

**Files:**
- Create: `frontend/src/app/shared/ui-state.ts`
- Create: `frontend/src/app/shared/alert.component.ts`
- Create: `frontend/src/app/shared/loading.component.ts`

- [ ] Crear tipos `UiStatus = 'idle' | 'loading' | 'success' | 'error'`.
- [ ] Crear componentes accesibles con `role=status` y `aria-live`.
- [ ] Reemplazar mensajes implícitos por estados visibles en las pantallas.
- [ ] Probar build y navegación básica.
- [ ] Commit: `feat: add accessible UI state components`.

### Task 3: Portal alumno — datos y navegación de progreso

**Files:**
- Modify: `frontend/src/app/portal/datos-personales/datos-personales.component.ts`
- Modify: `frontend/src/app/portal/solicitud.service.ts`
- Create: `frontend/src/app/shared/progress-stepper.component.ts`

- [ ] Cargar catálogos desde API en lugar de IDs hardcodeados cuando estén
  disponibles.
- [ ] Asociar todos los labels con controles y mostrar errores por campo.
- [ ] Añadir datos opcionales permitidos por API y mensajes de privacidad.
- [ ] Mostrar progreso Datos → Documentos → Confirmación → Seguimiento.
- [ ] Redirigir al siguiente paso después de guardar correctamente.
- [ ] Añadir estados loading/error/éxito y test del formulario.
- [ ] Commit: `feat: improve student personal data flow`.

### Task 4: Portal alumno — documentos, confirmación y subsanación

**Files:**
- Modify: `frontend/src/app/portal/documentos/documentos.component.ts`
- Modify: `frontend/src/app/portal/seguimiento/seguimiento.component.ts`
- Modify: `frontend/src/app/portal/solicitud.service.ts`

- [ ] Validar MIME y tamaño antes de solicitar URL.
- [ ] Mostrar estado por documento: pendiente, subiendo, cargado, error y
  observado.
- [ ] Capturar errores de hash, presigned URL y PUT con opción de reintento.
- [ ] Consultar la solicitud actual y requisitos antes de mostrar acciones.
- [ ] Añadir confirmación de presentación con versión y requisitos pendientes.
- [ ] Mostrar observaciones con motivo, documento y acción de reemplazo.
- [ ] Implementar reenvío usando versión actual y mostrar resultado.
- [ ] Añadir tests para rechazo de MIME/tamaño y estado de upload.
- [ ] Commit: `feat: improve student document and remediation flow`.

### Task 5: Panel de auditoría

**Files:**
- Modify: `frontend/src/app/auditoria/panel/panel.component.ts`
- Create: `frontend/src/app/auditoria/panel/panel.component.spec.ts`

- [ ] Añadir filtros por `EN_AUDITORIA` y `EN_REAUDITORIA`.
- [ ] Presentar cada solicitud con metadatos y contador de documentos.
- [ ] Sustituir `window.prompt` por formulario inline/modal accesible para
  motivo.
- [ ] Mostrar decisión seleccionada, motivo y documentos pendientes.
- [ ] Deshabilitar registro hasta completar todas las decisiones.
- [ ] Mostrar confirmación, errores de conflicto y refresco después de guardar.
- [ ] Probar que el payload no incluye `auditor_id` y que todas las decisiones
  se envían.
- [ ] Commit: `feat: redesign auditor review panel`.

### Task 6: Dashboard administrativo

**Files:**
- Modify: `frontend/src/app/admin/dashboard/dashboard.component.ts`
- Create: `frontend/src/app/admin/dashboard/dashboard.component.spec.ts`

- [ ] Crear tarjetas para total, estados, enviadas y fallidas.
- [ ] Añadir barra/lista visual por estado sin depender solo del color.
- [ ] Añadir loading, error con reintento y estado vacío.
- [ ] Mostrar fecha de actualización y enlace a auditoría cuando corresponda.
- [ ] Commit: `feat: improve administrative dashboard`.

### Task 7: Calidad, accesibilidad y entrega

**Files:**
- Modify: `frontend/src/index.html`
- Modify: `frontend/src/styles.scss`
- Modify: `README.md`
- Modify: `docs/OPERACION_PRODUCCION.md`

- [ ] Añadir idioma `es`, título y foco global coherentes.
- [ ] Revisar teclado, contraste, tamaños táctiles y responsive.
- [ ] Ejecutar `npm run build`.
- [ ] Ejecutar backend completo para asegurar que no hay regresiones.
- [ ] Ejecutar smoke contra `/health`, `/health/ready` y login desplegado.
- [ ] Documentar la nueva navegación y checklist E2E.
- [ ] Commit: `chore: verify FACE frontend UX and accessibility`.
