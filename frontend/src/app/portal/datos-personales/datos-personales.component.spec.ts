import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';
import { DatosPersonalesComponent } from './datos-personales.component';

describe('DatosPersonalesComponent', () => {
  let fixture: ComponentFixture<DatosPersonalesComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [DatosPersonalesComponent],
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    fixture = TestBed.createComponent(DatosPersonalesComponent);
    fixture.detectChanges();
  });

  it('el formulario empieza inválido y se habilita con los datos obligatorios', () => {
    const component = fixture.componentInstance;
    expect(component.form.valid).toBeFalse();
    component.form.setValue({
      apellido: 'Pérez', nombres: 'Ana', dni: '30123456',
      email: 'ana@example.com', celular: '+5493815555555',
      fecha_nacimiento: '2000-01-01', domicilio: 'Av. Independencia 1900', discapacidad: false,
      convocatoria_id: 1, carrera_id: 1, tipo_ingresante: 'nuevo', acepta_declaracion: false,
    });
    expect(component.form.valid).toBeFalse();
    component.form.controls.acepta_declaracion.setValue(true);
    expect(component.form.valid).toBeTrue();
    component.form.controls.convocatoria_id.setValue(0);
    expect(component.form.controls.convocatoria_id.invalid).toBeTrue();
    component.form.controls.carrera_id.setValue(0);
    expect(component.form.controls.carrera_id.invalid).toBeTrue();
  });
});
