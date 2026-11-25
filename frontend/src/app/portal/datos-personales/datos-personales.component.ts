import { Component, inject } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { SolicitudService } from '../solicitud.service';

@Component({
  selector: 'app-datos-personales',
  standalone: true,
  imports: [ReactiveFormsModule],
  template: `
    <div class="stack">
      <header>
        <p class="muted">Paso 1 de 3 · Datos personales</p>
        <h1>Comenzá tu preinscripción</h1>
        <p>Completá tus datos. Podrás revisar todo antes de confirmar.</p>
      </header>
      <form [formGroup]="form" (ngSubmit)="guardar()" novalidate>
        <div class="grid-2">
          <label for="apellido">Apellido
            <input id="apellido" formControlName="apellido" autocomplete="family-name">
            @if (form.controls.apellido.touched && form.controls.apellido.invalid) {
              <small class="error">Ingresá tu apellido.</small>
            }
          </label>
          <label for="nombres">Nombres
            <input id="nombres" formControlName="nombres" autocomplete="given-name">
            @if (form.controls.nombres.touched && form.controls.nombres.invalid) {
              <small class="error">Ingresá tus nombres.</small>
            }
          </label>
          <label for="dni">DNI
            <input id="dni" formControlName="dni" inputmode="numeric" autocomplete="off">
          </label>
          <label for="email">Correo electrónico
            <input id="email" formControlName="email" type="email" autocomplete="email">
          </label>
          <label for="celular">Celular
            <input id="celular" formControlName="celular" type="tel" autocomplete="tel">
          </label>
          <label for="tipo">Tipo de ingresante
            <select id="tipo" formControlName="tipo_ingresante">
              <option value="nuevo">Nuevo ingreso</option>
            </select>
          </label>
        </div>
        @if (error) { <p class="error" role="alert">{{ error }}</p> }
        @if (saved) { <p class="success" role="status">Datos guardados. Continuá con la documentación.</p> }
        <button type="submit" [disabled]="form.invalid || loading">
          {{ loading ? 'Guardando…' : 'Guardar y continuar' }}
        </button>
      </form>
    </div>
  `,
})
export class DatosPersonalesComponent {
  private fb = inject(FormBuilder);
  private service = inject(SolicitudService);
  form = this.fb.nonNullable.group({
    apellido: ['', Validators.required],
    nombres: ['', Validators.required],
    dni: ['', Validators.required],
    email: ['', [Validators.required, Validators.email]],
    celular: ['', Validators.required],
    convocatoria_id: [1, Validators.required],
    carrera_id: [1, Validators.required],
    tipo_ingresante: ['nuevo', Validators.required],
  });
  loading = false;
  saved = false;
  error = '';
  guardar() {
    if (this.form.invalid) { this.form.markAllAsTouched(); return; }
    this.loading = true; this.error = ''; this.saved = false;
    this.service.crear(this.form.getRawValue()).subscribe({
      next: sol => {
        localStorage.setItem('solicitudId', String(sol.id));
        this.loading = false; this.saved = true;
      },
      error: () => { this.loading = false; this.error = 'No pudimos guardar tus datos. Intentá nuevamente.'; },
    });
  }
}
