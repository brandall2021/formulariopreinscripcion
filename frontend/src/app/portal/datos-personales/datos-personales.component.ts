import { Component, inject } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { SolicitudService } from '../solicitud.service';

@Component({
  selector: 'app-datos-personales',
  standalone: true,
  imports: [ReactiveFormsModule],
  template: `
    <form [formGroup]="form" (ngSubmit)="guardar()">
      <label>Apellido <input formControlName="apellido"></label>
      <label>Nombres <input formControlName="nombres"></label>
      <label>DNI <input formControlName="dni"></label>
      <label>Correo <input formControlName="email" type="email"></label>
      <label>Celular <input formControlName="celular"></label>
      <button type="submit" [disabled]="form.invalid">Guardar borrador</button>
    </form>
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
  guardar() {
    if (this.form.valid) {
      this.service.crear(this.form.getRawValue()).subscribe(sol => {
        localStorage.setItem('solicitudId', String(sol.id));
      });
    }
  }
}
