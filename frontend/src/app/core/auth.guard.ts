import { CanActivateFn, Router } from '@angular/router';
import { inject } from '@angular/core';
import { AuthService } from './auth.service';

export function roleGuard(...roles: string[]): CanActivateFn {
  return () => {
    const auth = inject(AuthService);
    const router = inject(Router);
    if (auth.isLoggedIn() && (!roles.length || auth.hasRole(...roles))) return true;
    if (roles.includes('admin') || roles.includes('auditor')) {
      return router.createUrlTree(['/login/admin']);
    }
    return router.createUrlTree(['/login']);
  };
}
