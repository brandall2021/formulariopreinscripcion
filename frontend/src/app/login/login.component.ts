import { Component, inject } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router } from '@angular/router';
import { ApiService } from '../core/api.service';
import { AuthService } from '../core/auth.service';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [ReactiveFormsModule],
  template: `
    <h1>Ingreso por correo</h1>
    <p>Te enviaremos un código OTP para continuar tu preinscripción.</p>
    <form [formGroup]="emailForm" (ngSubmit)="requestOtp()">
      <label>Correo <input formControlName="email" type="email"></label>
      <button type="submit" [disabled]="emailForm.invalid || loading">Enviar código</button>
    </form>

    @if (sent) {
      <form [formGroup]="codeForm" (ngSubmit)="verifyOtp()">
        <label>Código <input formControlName="code" maxlength="6"></label>
        <button type="submit" [disabled]="codeForm.invalid || loading">Ingresar</button>
      </form>
    }
    @if (error) { <p class="error">{{ error }}</p> }
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
