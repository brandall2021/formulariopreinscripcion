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
