import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { DatosPersonalesComponent } from './datos-personales.component';

describe('DatosPersonalesComponent', () => {
  let fixture: ComponentFixture<DatosPersonalesComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [DatosPersonalesComponent],
      providers: [provideHttpClient(), provideHttpClientTesting()],
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
      convocatoria_id: 1, carrera_id: 1, tipo_ingresante: 'nuevo',
    });
    expect(component.form.valid).toBeTrue();
  });
});
