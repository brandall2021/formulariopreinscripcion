import { Component, inject } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { forkJoin, Observable } from 'rxjs';
import { SolicitudService } from '../solicitud.service';
import { validateDocument } from './document-validation';

type RequisitoVista = { tipo_documento_id: number; nombre: string };

@Component({
  selector: 'app-documentos',
  standalone: true,
  styles: [`
    .confirmacion { display: grid; justify-items: start; gap: 12px;
      border-top: 4px solid var(--navy); }
    .confirmacion h2, .confirmacion p { margin: 0; }
    .confirmacion button:disabled { opacity: 1; color: #34445c; background: #e2e8f0; }
    @media (max-width: 680px) {
      .confirmacion button { width: 100%; }
    }
  `],
  template: `
    <div class="stack">
      <header>
        <p class="muted">Paso 2 de 3 · Documentación</p>
        <h1>{{ corrigiendo ? 'Corregí tus documentos' : 'Subí tus documentos' }}</h1>
        <p>Se aceptan PDF, JPG y PNG de hasta 10 MB.</p>
      </header>
      @for (req of requisitos; track req.tipo_documento_id) {
        <section>
          <div style="display:flex;justify-content:space-between;gap:12px;align-items:start">
            <div><h2>{{ req.nombre }}</h2><p class="muted">Archivo obligatorio</p></div>
            <span class="status">{{ estados[req.tipo_documento_id] || 'Pendiente' }}</span>
          </div>
          @for (motivo of motivos[req.tipo_documento_id] ?? []; track $index) {
            <p class="error">{{ motivo }}</p>
          }
          <label [for]="'doc-' + req.tipo_documento_id">{{ corrigiendo ? 'Subir nueva versión' : 'Seleccionar archivo' }}
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
      <section class="confirmacion" aria-labelledby="confirmacion-titulo">
        <h2 id="confirmacion-titulo">{{ corrigiendo ? 'Reenviar documentación' : 'Confirmar preinscripción' }}</h2>
        <p class="muted">{{ corrigiendo ? 'Subí una nueva versión de cada documento observado y reenviá la solicitud. Las versiones anteriores se conservan en el historial.' : 'Cuando confirmes, la solicitud pasará a validación documental.' }}</p>
        <p id="confirmacion-progreso" role="status">
          @if (cargandoRequisitos) {
            Cargando los requisitos para confirmar…
          } @else if (requisitos.length) {
            {{ documentosCargados }} de {{ requisitos.length }} documentos {{ corrigiendo ? 'observados con nueva versión' : 'obligatorios cargados' }}.
            @if (documentosCargados < requisitos.length) {
              {{ corrigiendo ? 'Subí las nuevas versiones pendientes para habilitar el botón.' : 'Cargá los archivos pendientes para habilitar el botón.' }}
            }
          } @else {
            No hay requisitos disponibles para esta solicitud.
          }
        </p>
        <button type="button" aria-describedby="confirmacion-progreso" (click)="confirmar()"
          [disabled]="!puedeConfirmar">
          {{ confirmado ? 'Preinscripción confirmada' : (confirmando ? 'Enviando…' : (corrigiendo ? 'Reenviar documentación' : 'Confirmar preinscripción')) }}
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
  private route = inject(ActivatedRoute);
  solicitudId = Number(this.route.snapshot.paramMap.get('id') ?? localStorage.getItem('solicitudId'));
  cargandoRequisitos = true;
  corrigiendo = false;
  version = 1;
  motivos: Partial<Record<number, string[]>> = {};

  constructor() {
    if (!Number.isSafeInteger(this.solicitudId) || this.solicitudId <= 0) {
      this.errorCarga();
      return;
    }
    this.service.contextoCarga(this.solicitudId).subscribe({
      next: contexto => {
        if (contexto.estado !== 'BORRADOR' && contexto.estado !== 'PENDIENTE_ALUMNO') {
          void this.router.navigate(['/portal/seguimiento', this.solicitudId]);
          return;
        }
        this.version = contexto.version;
        this.corrigiendo = contexto.estado === 'PENDIENTE_ALUMNO';
        for (const id of contexto.cargados) this.estados[id] = 'Cargado';
        for (const obs of contexto.observaciones) {
          (this.motivos[obs.tipo_documento_id] ??= []).push(obs.motivo);
        }
        forkJoin({
          tipos: this.service.tiposDocumentos(),
          requisitos: this.service.requisitos(contexto.convocatoria_id, contexto.carrera_id, contexto.tipo_ingresante),
        }).subscribe({
          next: ({ tipos, requisitos }) => {
            const porId = new Map(tipos.map(item => [item.id, item]));
            const tiposRequeridos = this.corrigiendo
              ? Object.keys(this.motivos).map(Number)
              : [...new Set(requisitos.filter(req => req.obligatorio).map(req => req.tipo_documento_id))];
            if (!this.corrigiendo && contexto.discapacidad) {
              const cud = tipos.find(tipo => tipo.codigo === 'cud');
              if (!cud) {
                this.errorCarga();
                return;
              }
              if (!tiposRequeridos.includes(cud.id)) tiposRequeridos.push(cud.id);
            }
            this.requisitos = tiposRequeridos.map(id => ({
              tipo_documento_id: id,
              nombre: porId.get(id)?.nombre ?? 'Documento requerido',
            }));
            this.cargandoRequisitos = false;
          },
          error: () => this.errorCarga(),
        });
      },
      error: () => this.errorCarga(),
    });
  }

  private errorCarga() {
    this.cargandoRequisitos = false;
    this.errores[0] = 'No se pudo recuperar la documentación de tu solicitud.';
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
        this.mensaje = this.corrigiendo ? 'Nueva versión cargada correctamente.' : 'Documento cargado correctamente.';
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
    this.confirmando = true;
    delete this.errores[0];
    const enviar: Observable<unknown> = this.corrigiendo
      ? this.service.reenviar(this.solicitudId, this.version)
      : this.service.confirmar(this.solicitudId, this.version);
    enviar.subscribe({
      next: () => {
        this.confirmando = false;
        this.confirmado = true;

        this.router.navigate(['/portal/seguimiento', this.solicitudId]);
      },
      error: ({ error }) => {
        this.confirmando = false;
        this.errores[0] = typeof error?.detail === 'string' ? error.detail : 'No se pudo enviar la documentación. Intentá nuevamente.';
      },
    });
  }
}
