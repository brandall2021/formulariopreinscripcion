import { Component, inject } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router } from '@angular/router';
import { ApiService } from '../core/api.service';
import { AuthService } from '../core/auth.service';

@Component({
  selector: 'app-admin-login',
  standalone: true,
  imports: [ReactiveFormsModule],
  template: `
    <h1>Acceso administrativo</h1>
    <form [formGroup]="form" (ngSubmit)="submit()">
      <label>Email <input formControlName="email" type="email"></label>
      <label>Contraseña <input formControlName="password" type="password"></label>
      <button type="submit" [disabled]="form.invalid || loading">Ingresar</button>
    </form>
    @if (error) { <p class="error">{{ error }}</p> }
  `,
})
export class AdminLoginComponent {
  private fb = inject(FormBuilder);
  private api = inject(ApiService);
  private auth = inject(AuthService);
  private router = inject(Router);
  loading = false;
  error = '';
  form = this.fb.nonNullable.group({
    email: ['', [Validators.required, Validators.email]],
    password: ['', Validators.required],
  });

  submit() {
    if (this.form.invalid) return;
    this.loading = true; this.error = '';
    this.api.post<{ access_token: string }>('/auth/admin/login', this.form.getRawValue()).subscribe({
      next: ({ access_token }) => {
        this.auth.setToken(access_token);
        const rol = this.auth.role();
        this.loading = false;
        this.router.navigateByUrl(rol === 'auditor' ? '/auditoria' : '/admin');
      },
      error: () => { this.error = 'Credenciales inválidas.'; this.loading = false; },
    });
  }
}
