import { ComponentFixture, TestBed } from '@angular/core/testing';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';
import { environment } from '../../../environments/environment';
import { PanelComponent } from './panel.component';

describe('PanelComponent', () => {
  let fixture: ComponentFixture<PanelComponent>;
  let httpMock: HttpTestingController;
  const base = environment.apiUrl;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [PanelComponent],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    fixture = TestBed.createComponent(PanelComponent);
    httpMock = TestBed.inject(HttpTestingController);
    fixture.detectChanges();
    httpMock.expectOne(`${base}/catalogos/carreras`).flush([]);
  });

  afterEach(() => httpMock.verify());

  it('muestra el estado vacío hasta cargar solicitudes', () => {
    expect(fixture.nativeElement.textContent).toContain('Sin solicitudes');
    httpMock.expectOne(`${base}/auditorias/solicitudes`).flush([]);
  });

  it('muestra EN_AUDITORIA y EN_REAUDITORIA de la consulta sin filtro', () => {
    const req = httpMock.expectOne(`${base}/auditorias/solicitudes`);
    expect(req.request.method).toBe('GET');
    expect(req.request.urlWithParams).toBe(`${base}/auditorias/solicitudes`);
    req.flush([
      { id: 1, numero: 'FACE-1', dni: '111', carrera: 'A', estado: 'EN_AUDITORIA' },
      { id: 2, numero: 'FACE-2', dni: '222', carrera: 'B', estado: 'EN_REAUDITORIA' },
    ]);
    fixture.detectChanges();
    const texto = fixture.nativeElement.textContent;
    expect(texto).toContain('EN_AUDITORIA');
    expect(texto).toContain('EN_REAUDITORIA');
  });

  it('registra un único lote con todas las decisiones y sus versiones', () => {
    httpMock.expectOne(`${base}/auditorias/solicitudes`).flush([
      { id: 1, numero: 'FACE-1', dni: '111', carrera: 'A', estado: 'EN_AUDITORIA' },
    ]);
    fixture.detectChanges();
    const component = fixture.componentInstance;
    const fila = component.filas[0];

    component.cargarDocumentos(fila);
    httpMock.expectOne(`${base}/auditorias/solicitudes/1/documentos`).flush([
      { documento_id: 11, version: 1, estado: 'EN_REVISION',
        object_key: null, observaciones: [] },
      { documento_id: 12, version: 2, estado: 'EN_REVISION',
        object_key: null, observaciones: [] },
    ]);
    fixture.detectChanges();
    expect(component.puedeRegistrar(fila)).toBeFalse();

    component.aprobar(fila, component.documentos[1][0]);
    component.setMotivo(fila, component.documentos[1][1], 'Ilegible');
    component.observar(fila, component.documentos[1][1]);
    expect(component.puedeRegistrar(fila)).toBeTrue();

    component.registrar(fila);
    const post = httpMock.expectOne(`${base}/auditorias/solicitudes/1`);
    expect(post.request.method).toBe('POST');
    expect(post.request.body.decisiones).toEqual([
      { documento_id: 11, version: 1, resultado: 'APROBADO' },
      { documento_id: 12, version: 2, resultado: 'OBSERVADO', motivo: 'Ilegible' },
    ]);
    post.flush({});
    expect(component.documentos[1]).toBeUndefined();
    expect(component.selecciones[1]).toBeUndefined();
    expect(component.filas).toEqual([]);
  });
});
