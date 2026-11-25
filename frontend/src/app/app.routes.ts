import { Routes } from '@angular/router';
import { roleGuard } from './core/auth.guard';

export const routes: Routes = [
  { path: 'login', loadComponent: () =>
      import('./login/login.component').then(m => m.LoginComponent) },
  { path: 'login/admin', loadComponent: () =>
      import('./login/admin-login.component').then(m => m.AdminLoginComponent) },
  { path: 'portal/datos', canActivate: [roleGuard('alumno')], loadComponent: () =>
      import('./portal/datos-personales/datos-personales.component')
        .then(m => m.DatosPersonalesComponent) },
  { path: 'portal/documentos/:id', canActivate: [roleGuard('alumno')], loadComponent: () =>
      import('./portal/documentos/documentos.component')
        .then(m => m.DocumentosComponent) },
  { path: 'portal/documentos', canActivate: [roleGuard('alumno')], loadComponent: () =>
      import('./portal/documentos/documentos.component')
        .then(m => m.DocumentosComponent) },
  { path: 'portal/seguimiento/:id', canActivate: [roleGuard('alumno')], loadComponent: () =>
      import('./portal/seguimiento/seguimiento.component')
        .then(m => m.SeguimientoComponent) },
  { path: 'auditoria', canActivate: [roleGuard('auditor', 'admin')], loadComponent: () =>
      import('./auditoria/panel/panel.component').then(m => m.PanelComponent) },
  { path: 'admin', canActivate: [roleGuard('admin')], loadComponent: () =>
      import('./admin/dashboard/dashboard.component').then(m => m.DashboardComponent) },
  { path: '', pathMatch: 'full', redirectTo: 'login' },
];
