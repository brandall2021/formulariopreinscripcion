import { Component, inject } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router } from '@angular/router';
import { ApiService } from '../core/api.service';
import { AuthService } from '../core/auth.service';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [ReactiveFormsModule],
  styles: [`
    .intro { background: white; border-bottom: 1px solid var(--line); }
    .intro-inner, .login-content { width: min(100%, 1152px); margin-inline: auto;
      padding-inline: clamp(16px, 3vw, 24px); }
    .intro-inner { padding-block: clamp(32px, 5vw, 48px); }
    .intro p { margin: 0; }
    .institution { color: #bd0814; font-size: .875rem; font-weight: 650; }
    h1 { margin-block: 12px; }
    .login-content { display: grid; gap: 16px; padding-top: 32px; }
    form { max-width: 560px; }
  `],
  template: `
    <div class="intro">
      <div class="intro-inner">
        <p class="institution">Facultad de Ciencias Económicas - UNT</p>
        <h1>Formulario de preinscripción</h1>
        <p>Ingresá tu correo para iniciar o continuar el trámite.</p>
      </div>
    </div>
    <div class="login-content">

    <form [formGroup]="emailForm" (ngSubmit)="requestOtp()">
      <h2>Ingreso por correo</h2>
      <label>Correo electrónico <input formControlName="email" type="email" autocomplete="email"></label>
      <button type="submit" [disabled]="emailForm.invalid || loading">Enviar código</button>
    </form>

    @if (sent) {
      <form [formGroup]="codeForm" (ngSubmit)="verifyOtp()">
        <label>Código <input formControlName="code" inputmode="numeric" autocomplete="one-time-code" maxlength="6"></label>
        <button type="submit" [disabled]="codeForm.invalid || loading">Ingresar</button>
      </form>
    }
    @if (error) { <p class="error">{{ error }}</p> }
    </div>
  `,
})
export class LoginComponent {
  private fb = inject(FormBuilder);
  private api = inject(ApiService);
  private auth = inject(AuthService);
  private router = inject(Router);
  loading = false;
  sent = false;
  error = '';

  emailForm = this.fb.nonNullable.group({
    email: ['', [Validators.required, Validators.email]],
  });
  codeForm = this.fb.nonNullable.group({
    code: ['', [Validators.required, Validators.pattern(/^\d{6}$/)]],
  });

  requestOtp() {
    if (this.emailForm.invalid) return;
    this.loading = true; this.error = '';
    this.api.post('/auth/request-otp', this.emailForm.getRawValue()).subscribe({
      next: () => { this.sent = true; this.loading = false; },
      error: () => { this.error = 'No se pudo enviar el código.'; this.loading = false; },
    });
  }

  verifyOtp() {
    if (this.emailForm.invalid || this.codeForm.invalid) return;
    this.loading = true; this.error = '';
    const payload = { ...this.emailForm.getRawValue(), ...this.codeForm.getRawValue() };
    this.api.post<{ access_token: string }>('/auth/verify-otp', payload).subscribe({
      next: ({ access_token }) => {
        this.auth.setToken(access_token);
        this.loading = false;
        this.router.navigateByUrl('/portal/datos');
      },
      error: () => { this.error = 'Código inválido o vencido.'; this.loading = false; },
    });
  }
}
