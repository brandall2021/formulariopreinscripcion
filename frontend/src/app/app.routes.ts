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
  { path: 'auditoria', loadComponent: () =>
      import('./auditoria/panel/panel.component').then(m => m.PanelComponent) },
  { path: 'admin', loadComponent: () =>
      import('./admin/dashboard/dashboard.component').then(m => m.DashboardComponent) },
  { path: '', pathMatch: 'full', redirectTo: 'portal/datos' },
];
