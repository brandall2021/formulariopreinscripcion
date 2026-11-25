import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { SolicitudService } from './solicitud.service';

describe('SolicitudService', () => {
  let service: SolicitudService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [SolicitudService, provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(SolicitudService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('obtiene convocatorias activas del catálogo', () => {
    service.convocatorias().subscribe(items => expect(items[0].id).toBe(1));
    const request = http.expectOne(req => req.url.endsWith('/catalogos/convocatorias'));
    expect(request.request.method).toBe('GET');
    request.flush([{ id: 1, nombre: 'Convocatoria 2026', anio: 2026, activa: true }]);
  });

  it('obtiene carreras activas del catálogo', () => {
    service.carreras().subscribe(items => expect(items[0].codigo).toBe('CP'));
    const request = http.expectOne(req => req.url.endsWith('/catalogos/carreras'));
    request.flush([{ id: 1, nombre: 'Contador Público', codigo: 'CP', activa: true }]);
  });

  it('obtiene requisitos con los filtros de la solicitud', () => {
    service.requisitos(2, 3, 'nuevo').subscribe(items => expect(items[0].tipo_documento_id).toBe(9));
    const request = http.expectOne(req =>
      req.url.endsWith('/catalogos/requisitos')
      && req.params.get('convocatoria_id') === '2'
      && req.params.get('carrera_id') === '3'
      && req.params.get('tipo_ingresante') === 'nuevo');
    expect(request.request.method).toBe('GET');
    request.flush([{ id: 1, convocatoria_id: 2, carrera_id: 3,
      tipo_ingresante: 'nuevo', tipo_documento_id: 9, obligatorio: true }]);
  });
});
