import { Component, inject } from '@angular/core';
import { Router } from '@angular/router';
import { Requisito, SolicitudService } from '../solicitud.service';
import { validateDocument } from './document-validation';

type RequisitoVista = Requisito & { nombre: string; descripcion?: string };

@Component({
  selector: 'app-documentos',
  standalone: true,
  template: `
    <div class="stack">
      <header>
        <p class="muted">Paso 2 de 3 · Documentación</p>
        <h1>Subí tus documentos</h1>
        <p>Se aceptan PDF, JPG y PNG de hasta 10 MB.</p>
      </header>
      @for (req of requisitos; track req.tipo_documento_id) {
        <section>
          <div style="display:flex;justify-content:space-between;gap:12px;align-items:start">
            <div><h2>{{ req.nombre }}</h2><p class="muted">Archivo obligatorio</p></div>
            <span class="status">{{ estados[req.tipo_documento_id] || 'Pendiente' }}</span>
          </div>
          <label [for]="'doc-' + req.tipo_documento_id">Seleccionar archivo
            <input [id]="'doc-' + req.tipo_documento_id" type="file" accept=".pdf,.jpg,.jpeg,.png"
                   [disabled]="confirmando || confirmado || estados[req.tipo_documento_id] === 'Subiendo…'"
                   (change)="subir(req.tipo_documento_id, $event)">
          </label>
          @if (errores[req.tipo_documento_id]) { <p class="error" role="alert">{{ errores[req.tipo_documento_id] }}</p> }
        </section>
      } @empty {
        <p class="card" role="status">
          {{ cargandoRequisitos ? 'Cargando requisitos…' : 'No hay requisitos disponibles.' }}
        </p>
      }
      <section>
        <h2>Confirmar preinscripción</h2>
        <p class="muted">Cuando confirmes, la solicitud pasará a validación documental.</p>
        <button type="button" (click)="confirmar()"
          [disabled]="!puedeConfirmar">
          {{ confirmado ? 'Preinscripción confirmada' : (confirmando ? 'Confirmando…' : 'Confirmar preinscripción') }}
        </button>
        @if (errores[0]) { <p class="error" role="alert">{{ errores[0] }}</p> }
      </section>
      @if (mensaje) { <p class="success" role="status">{{ mensaje }}</p> }
    </div>
  `,
})
export class DocumentosComponent {
  private service = inject(SolicitudService);
  private router = inject(Router);
  requisitos: RequisitoVista[] = [];
  estados: Record<number, string> = {};
  errores: Record<number, string> = {};
  mensaje = '';
  confirmando = false;
  confirmado = false;
  solicitudId = Number(localStorage.getItem('solicitudId') ?? 0);
  cargandoRequisitos = true;
  constructor() {
    const convocatoria = Number(localStorage.getItem('convocatoriaId') ?? 0);
    const carrera = Number(localStorage.getItem('carreraId') ?? 0);
    const tipo = localStorage.getItem('tipoIngresante') ?? 'nuevo';
    this.service.tiposDocumentos().subscribe({
      next: tipos => this.service.requisitos(convocatoria, carrera, tipo).subscribe({
        next: requisitos => {
          const porId = new Map(tipos.map(item => [item.id, item]));
          this.requisitos = requisitos.filter(item => item.obligatorio).map(item => ({
            ...item, nombre: porId.get(item.tipo_documento_id)?.nombre ?? 'Documento requerido',
            descripcion: porId.get(item.tipo_documento_id)?.descripcion,
          }));
          this.cargandoRequisitos = false;
        },
        error: () => { this.cargandoRequisitos = false; this.errores[0] = 'No se pudieron cargar los requisitos.'; },
      }),
      error: () => { this.cargandoRequisitos = false; this.errores[0] = 'No se pudieron cargar los tipos de documento.'; },
    });
  }
  get documentosCargados() {
    return this.requisitos.filter(req => this.estados[req.tipo_documento_id] === 'Cargado').length;
  }

  subir(tipoDocumentoId: number, event: Event) {
    const archivo = (event.target as HTMLInputElement).files?.[0];
    if (!archivo) return;
    this.errores[tipoDocumentoId] = '';
    const validation = validateDocument(archivo);
    if (!validation.valid) {
      this.errores[tipoDocumentoId] = validation.error;
      return;
    }
    this.estados[tipoDocumentoId] = 'Subiendo…';
    this.service.subirDocumento(this.solicitudId, tipoDocumentoId, archivo).subscribe({
      next: () => {
        this.estados[tipoDocumentoId] = 'Cargado';
        this.mensaje = 'Documento cargado correctamente.';
      },
      error: ({ status, error }) => {
        this.estados[tipoDocumentoId] = 'Error';
        this.errores[tipoDocumentoId] = status === 413
          ? 'El archivo supera el tamaño permitido.'
          : typeof error?.detail === 'string'
            ? error.detail
            : 'No se pudo subir el archivo. Intentá nuevamente.';
        (event.target as HTMLInputElement).value = '';
      },
    });
  }

  get puedeConfirmar() {
    return this.solicitudId > 0 && !this.cargandoRequisitos && this.requisitos.length > 0
      && this.documentosCargados === this.requisitos.length && !this.confirmando && !this.confirmado;
  }

  confirmar() {
    if (!this.puedeConfirmar) return;
    const version = Number(localStorage.getItem('solicitudVersion') ?? 1);
    this.confirmando = true;
    this.service.confirmar(this.solicitudId, version).subscribe({
      next: result => {
        this.confirmando = false;
        this.confirmado = true;
        localStorage.setItem('solicitudVersion', String((Number(localStorage.getItem('solicitudVersion') ?? 1)) + 1));
        this.mensaje = `Preinscripción confirmada: ${result.numero}.`;
        this.router.navigate(['/portal/seguimiento', this.solicitudId]);
      },
      error: () => {
        this.confirmando = false;
        this.errores[0] = 'No se pudo confirmar. Verificá que todos los documentos estén cargados.';
      },
    });
  }
}
