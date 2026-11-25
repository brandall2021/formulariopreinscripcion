# FACE Frontend — Diseño y funcionalidad

## Objetivo

Convertir el frontend Angular en una experiencia clara, accesible y usable para
alumnos, auditores y administradores, manteniendo los endpoints existentes y
sin inventar datos oficiales de FACE.

## Alcance

- Sistema visual consistente: colores institucionales sobrios, tipografía,
  tarjetas, botones, estados y responsive móvil.
- Navegación común con identidad de usuario, cierre de sesión y acceso según rol.
- Portal alumno:
  - formulario accesible con mensajes de validación;
  - progreso de preinscripción;
  - carga real de archivos con validación MIME/tamaño, progreso y errores;
  - confirmación explícita;
  - seguimiento de estados, observaciones, subsanación y reenvío.
- Auditoría:
  - filtros por estado;
  - tarjetas de solicitudes;
  - tabla documental con decisiones visibles;
  - motivo de observación en formulario, no `window.prompt`;
  - estados de carga, éxito y error.
- Administración:
  - indicadores por estado;
  - resumen de notificaciones;
  - estado vacío y error recuperable.
- Accesibilidad: labels asociados, foco visible, `aria-live`, contraste,
  navegación por teclado y no depender solo del color.

## Restricciones

- Angular 20 standalone components.
- No agregar una librería visual pesada.
- Mantener `ApiService`, interceptor Bearer, guards y endpoints actuales.
- No exponer documentos mediante URLs distintas de las entregadas por API.
- Validar archivos con MIME permitido y máximo `10485760` bytes.
- No cambiar decisiones de negocio ni datos seed.

## Criterios de aceptación

- El alumno puede completar el flujo principal desde móvil sin depender de
  mensajes del navegador.
- Cada acción muestra loading, resultado o error entendible.
- El auditor puede revisar una solicitud completa y registrar todas las
  decisiones sin usar `prompt`.
- El administrador entiende volumen, estados y fallas de notificación en menos
  de una pantalla.
- `npm run build` y las pruebas existentes pasan.
