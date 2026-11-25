import { Component, inject } from '@angular/core';
import { Router } from '@angular/router';
import { SolicitudService } from '../solicitud.service';
import { sha256 } from './checksum';
import { validateDocument } from './document-validation';

const REQUISITOS = [
  { id: 1, codigo: 'dni', nombre: 'DNI (frente y dorso)' },
  { id: 2, codigo: 'foto_carnet', nombre: 'Foto carnet' },
  { id: 3, codigo: 'acta_nacimiento', nombre: 'Acta de nacimiento' },
  { id: 4, codigo: 'titulo_secundario', nombre: 'Título secundario' },
  { id: 5, codigo: 'formulario_siu', nombre: 'Formulario SIU Guaraní' },
  { id: 6, codigo: 'comprobante_pago', nombre: 'Comprobante de pago' },
];

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
      @for (req of requisitos; track req.id) {
        <section>
          <div style="display:flex;justify-content:space-between;gap:12px;align-items:start">
            <div><h2>{{ req.nombre }}</h2><p class="muted">Archivo obligatorio</p></div>
            <span class="status">{{ estados[req.id] || 'Pendiente' }}</span>
          </div>
          <label [for]="'doc-' + req.id">Seleccionar archivo
            <input [id]="'doc-' + req.id" type="file" accept=".pdf,.jpg,.jpeg,.png"
                   (change)="subir(req.id, $event)">
          </label>
          @if (errores[req.id]) { <p class="error" role="alert">{{ errores[req.id] }}</p> }
        </section>
      } @empty { <p class="card">No hay requisitos disponibles.</p> }
      <section>
        <h2>Confirmar preinscripción</h2>
        <p class="muted">Cuando confirmes, la solicitud pasará a validación documental.</p>
        <button type="button" (click)="confirmar()"
          [disabled]="documentosCargados !== requisitos.length || confirmando || confirmado">
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
  requisitos = REQUISITOS;
  estados: Record<number, string> = {};
  errores: Record<number, string> = {};
  mensaje = '';
  confirmando = false;
  confirmado = false;
  solicitudId = Number(localStorage.getItem('solicitudId') ?? 0);
  get documentosCargados() {
    return this.requisitos.filter(req => this.estados[req.id] === 'Cargado').length;
  }

  async subir(tipoDocumentoId: number, event: Event) {
    const archivo = (event.target as HTMLInputElement).files?.[0];
    if (!archivo) return;
    this.errores[tipoDocumentoId] = '';
    const validation = validateDocument(archivo);
    if (!validation.valid) {
      this.errores[tipoDocumentoId] = validation.error;
      return;
    }
    this.estados[tipoDocumentoId] = 'Subiendo…';
    const checksum = await sha256(archivo);
    this.service.pedirUrlSubida({
      solicitud_id: this.solicitudId, tipo_documento_id: tipoDocumentoId,
      filename: archivo.name, content_type: archivo.type,
      size: archivo.size, checksum,
    }).subscribe({
      next: ({ url }) => {
        fetch(url, { method: 'PUT', body: archivo,
          headers: { 'Content-Type': archivo.type } })
          .then(response => {
            if (!response.ok) throw new Error('upload');
            this.estados[tipoDocumentoId] = 'Cargado';
            this.mensaje = 'Documento cargado correctamente.';
          })
          .catch(() => {
            this.estados[tipoDocumentoId] = 'Error';
            this.errores[tipoDocumentoId] = 'No se pudo subir el archivo. Intentá nuevamente.';
          });
      },
      error: () => {
        this.estados[tipoDocumentoId] = 'Error';
        this.errores[tipoDocumentoId] = 'No se pudo preparar la carga. Intentá nuevamente.';
      },
    });
  }

  confirmar() {
    if (this.documentosCargados !== this.requisitos.length || this.confirmando) return;
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
