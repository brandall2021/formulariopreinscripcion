import { Injectable } from '@angular/core';

export interface AuthClaims {
  sub?: string;
  rol?: string;
  exp?: number;
}

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly key = 'face_token';

  get token(): string | null {
    return localStorage.getItem(this.key);
  }

  setToken(token: string): void {
    localStorage.setItem(this.key, token);
  }

  clear(): void {
    localStorage.removeItem(this.key);
  }

  claims(): AuthClaims | null {
    const token = this.token;
    if (!token) return null;
    const parts = token.split('.');
    if (parts.length < 2) return null;
    try {
      const json = atob(parts[1].replace(/-/g, '+').replace(/_/g, '/'));
      return JSON.parse(decodeURIComponent(escape(json))) as AuthClaims;
    } catch {
      return null;
    }
  }

  role(): string | null {
    const claims = this.claims();
    if (!claims) return null;
    return claims.rol ?? (claims.sub ? 'alumno' : null);
  }

  isLoggedIn(): boolean {
    const claims = this.claims();
    if (!claims) return false;
    if (!claims.exp) return true;
    return claims.exp * 1000 > Date.now();
  }

  hasRole(...roles: string[]): boolean {
    const role = this.role();
    return !!role && roles.includes(role);
  }
}
