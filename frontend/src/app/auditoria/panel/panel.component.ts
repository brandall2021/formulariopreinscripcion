import { Component, DestroyRef, OnInit, inject } from '@angular/core';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ApiService } from '../../core/api.service';

interface Fila {
  id: number;
  numero: string;
  dni: string;
  carrera: string;
  estado: string;
}

interface Doc {
  documento_id: number;
  version: number;
  estado: string;
  object_key: string | null;
  observaciones: string[];
}

interface Aprobacion {
  auditoria_id: number;
  documento_id: number;
  solicitud: string | null;
  alumno: string;
  documento: string;
  version: number;
  auditor: string;
  fecha: string;
}

const fechaArgentina = new Intl.DateTimeFormat('es-AR', {
  timeZone: 'America/Argentina/Buenos_Aires',
  dateStyle: 'short', timeStyle: 'medium',
});

type DecisionLocal = { resultado: 'APROBADO' | 'OBSERVADO'; motivo?: string };

@Component({
  selector: 'app-panel',
  standalone: true,
  styles: [`
    .tabla-aprobaciones { overflow-x: auto; }
    table { width: 100%; border-collapse: collapse; text-align: left; }
    th, td { padding: 8px; border-bottom: 1px solid var(--line); }
    .vista { display: grid; gap: 10px; margin-block: 12px; }
    .vista iframe { display: block; width: 100%; height: min(70vh, 720px); border: 1px solid var(--line); }
    .vista img { display: block; max-width: 100%; max-height: 70vh; object-fit: contain; }
    .decision { margin-block: 12px 24px; padding-top: 12px; border-top: 1px solid var(--line); }
  `],
  template: `
    <h1>Auditoría documental</h1>
    <details class="card">
      <summary>Exportar legajo del alumno</summary>
      <p>El ZIP incluye los datos del alumno, sus solicitudes y todas las versiones disponibles de los documentos. El archivo legajo.json identifica las versiones faltantes.</p>
      <label>Seleccioná una solicitud del alumno
        <select #solicitudExportar>
          <option value="">Seleccioná una solicitud</option>
          @for (sol of solicitudesExportables; track sol.id) {
            <option [value]="sol.id">{{ sol.numero || ('Borrador ' + sol.id) }} · DNI {{ sol.dni }}</option>
          }
        </select>
      </label>
      <button type="button" (click)="exportarLegajo(solicitudExportar.value)" [disabled]="exportando">
        {{ exportando ? 'Preparando legajo…' : 'Exportar legajo ZIP' }}
      </button>
      @if (errorExportacion) { <p role="alert">{{ errorExportacion }}</p> }
    </details>
    <details class="card" (toggle)="alAlternarHistorial($event)">
      <summary>Auditoría de aprobación</summary>
      @if (cargandoAprobaciones) { <p role="status">Cargando aprobaciones…</p> }
      @else if (errorAprobaciones) {
        <p role="alert">{{ errorAprobaciones }}</p>
        <button type="button" (click)="cargarAprobaciones()">Reintentar</button>
      } @else if (aprobaciones.length) {
        <div class="tabla-aprobaciones">
          <table aria-label="Historial de aprobación de documentos">
            <thead>
              <tr>
                <th scope="col">Solicitud</th><th scope="col">Alumno</th>
                <th scope="col">Documento</th><th scope="col">Aprobó</th>
                <th scope="col">Fecha y hora (Argentina)</th>
              </tr>
            </thead>
            <tbody>
              @for (fila of aprobaciones; track fila.auditoria_id + ':' + fila.documento_id) {
                <tr>
                  <td>{{ fila.solicitud }}</td><td>{{ fila.alumno }}</td>
                  <td>{{ fila.documento }} · v{{ fila.version }}</td><td>{{ fila.auditor }}</td>
                  <td><time [attr.datetime]="fila.fecha">{{ formatearFecha(fila.fecha) }}</time></td>
                </tr>
              }
            </tbody>
          </table>
        </div>
      } @else { <p>No hay aprobaciones registradas.</p> }
    </details>
    @for (fila of filas; track fila.numero) {
      <article>
        <strong>{{ fila.numero }}</strong> — {{ fila.dni }} — {{ fila.estado }}
        <button (click)="cargarDocumentos(fila)">Auditar</button>
        @if (documentos[fila.id]) {
          <h2>Documentos presentados</h2>
          <ul>
            @for (doc of documentos[fila.id]; track doc.documento_id) {
              <li>
                Documento {{ doc.documento_id }} v{{ doc.version }} ({{ doc.estado }})
                @for (motivo of doc.observaciones; track motivo) { <em>{{ motivo }}</em> }
                <button type="button" (click)="previsualizar(doc)" [disabled]="cargandoArchivo"
                  [attr.aria-expanded]="vista?.id === doc.documento_id">
                  {{ cargandoArchivo === doc.documento_id ? 'Abriendo…' : 'Ver archivo' }}
                </button>
                @if (erroresArchivo[doc.documento_id]; as mensaje) {
                  <p role="alert">{{ mensaje }}</p>
                }
                @if (vista; as archivo) {
                  @if (archivo.id === doc.documento_id) {
                    <div class="vista">
                      <button type="button" (click)="cerrarVista()">Cerrar vista previa</button>
                      @if (archivo.pdf; as pdf) {
                        <iframe [src]="pdf" [title]="'Vista previa del documento ' + doc.documento_id"></iframe>
                      } @else {
                        <img [src]="archivo.url" [alt]="'Vista previa del documento ' + doc.documento_id">
                      }
                    </div>
                  }
                }
                <div class="decision">
                  <h3>Decisión de auditoría</h3>
                  @if (selecciones[fila.id]?.[doc.documento_id]; as decision) {
                    <p role="status">Decisión seleccionada: {{ decision.resultado }}</p>
                  }
                <button type="button" (click)="aprobar(fila, doc)">Aprobar</button>
                <label>Motivo si observás
                  <textarea rows="2" [value]="motivos[fila.id]?.[doc.documento_id] || ''"
                    (input)="setMotivo(fila, doc, $any($event.target).value)"></textarea>
                </label>
                <button type="button" (click)="observar(fila, doc)"
                  [disabled]="!(motivos[fila.id]?.[doc.documento_id] || '').trim()">
                  Observar documento
                </button>
                </div>
              </li>
            }
          </ul>
          <button [disabled]="!puedeRegistrar(fila)" (click)="registrar(fila)">
            Registrar auditoría
          </button>
        }
      </article>
    } @empty {
      <p>Sin solicitudes</p>
    }
  `,
})
export class PanelComponent implements OnInit {
  private api = inject(ApiService);
  filas: Fila[] = [];
  solicitudesExportables: Fila[] = [];
  exportando = false;
  errorExportacion = '';
  documentos: Record<number, Doc[]> = {};
  selecciones: Record<number, Record<number, DecisionLocal>> = {};
  motivos: Record<number, Record<number, string>> = {};

  private sanitizer = inject(DomSanitizer);
  private destroyRef = inject(DestroyRef);
  vista: { id: number; url: string; pdf: SafeResourceUrl | null } | null = null;
  cargandoArchivo = 0;
  erroresArchivo: Record<number, string> = {};

  constructor() {
    this.destroyRef.onDestroy(() => this.cerrarVista());
  }

  cerrarVista() {
    if (this.vista) URL.revokeObjectURL(this.vista.url);
    this.vista = null;
  }

  previsualizar(doc: Doc) {
    const id = doc.documento_id;
    this.cerrarVista();
    this.cargandoArchivo = id;
    delete this.erroresArchivo[id];
    this.api.descargar(`/documentos/${id}/archivo`)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: archivo => {
          this.cargandoArchivo = 0;
          if (!['application/pdf', 'image/jpeg', 'image/png'].includes(archivo.type)) {
            this.erroresArchivo[id] = 'Este formato no admite vista previa.';
            return;
          }
          const url = URL.createObjectURL(archivo);
          this.vista = { id, url, pdf: archivo.type === 'application/pdf'
            ? this.sanitizer.bypassSecurityTrustResourceUrl(url)
            : null };
        },
        error: ({ status }) => {
          this.cargandoArchivo = 0;
          this.erroresArchivo[id] = status === 404
            ? 'El archivo validado no está disponible.'
            : 'No se pudo abrir el archivo. Intentá nuevamente.';
        },
      });
  }
  aprobaciones: Aprobacion[] = [];
  cargandoAprobaciones = false;
  errorAprobaciones = '';
  private historialAbierto = false;

  formatearFecha(fecha: string) {
    return fechaArgentina.format(new Date(fecha));
  }

  alAlternarHistorial(evento: Event) {
    this.historialAbierto = (evento.currentTarget as HTMLDetailsElement).open;
    if (this.historialAbierto) this.cargarAprobaciones();
  }

  cargarAprobaciones() {
    if (this.cargandoAprobaciones) return;
    this.cargandoAprobaciones = true;
    this.errorAprobaciones = '';
    this.api.get<Aprobacion[]>('/auditorias/aprobaciones')
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: filas => {
          this.aprobaciones = filas;
          this.cargandoAprobaciones = false;
        },
        error: () => {
          this.errorAprobaciones = 'No se pudo cargar el historial de aprobaciones.';
          this.cargandoAprobaciones = false;
        },
      });
  }

  ngOnInit() {
    this.api.get<Fila[]>('/auditorias/solicitudes')
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: filas => {
          this.solicitudesExportables = filas;
          this.filas = filas.filter(f => f.estado === 'EN_AUDITORIA' || f.estado === 'EN_REAUDITORIA');
        },
        error: () => { this.errorExportacion = 'No se pudo cargar el listado de solicitudes.'; },
      });
  }

  exportarLegajo(solicitud: string) {
    if (this.exportando) return;
    if (!solicitud) {
      this.errorExportacion = 'Seleccioná una solicitud para exportar el legajo.';
      return;
    }
    this.exportando = true;
    this.errorExportacion = '';
    this.api.descargar(`/auditorias/solicitudes/${solicitud}/legajo`)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: archivo => {
          const url = URL.createObjectURL(archivo);
          const enlace = document.createElement('a');
          enlace.href = url;
          enlace.download = `legajo-solicitud-${solicitud}.zip`;
          enlace.click();
          setTimeout(() => URL.revokeObjectURL(url), 1000);
          this.exportando = false;
        },
        error: () => {
          this.exportando = false;
          this.errorExportacion = 'No se pudo exportar el legajo. Intentá nuevamente.';
        },
      });
  }

  cargarDocumentos(fila: Fila) {
    this.api.get<Doc[]>(`/auditorias/solicitudes/${fila.id}/documentos`)
      .subscribe(docs => {
        this.documentos[fila.id] = docs;
        this.selecciones[fila.id] = {};
      });
  }

  aprobar(fila: Fila, doc: Doc) {
    this.selecciones[fila.id] ??= {};
    this.selecciones[fila.id][doc.documento_id] = { resultado: 'APROBADO' };
  }

  setMotivo(fila: Fila, doc: Doc, motivo: string) {
    this.motivos[fila.id] ??= {};
    this.motivos[fila.id][doc.documento_id] = motivo;
  }
  observar(fila: Fila, doc: Doc) {
    const motivo = this.motivos[fila.id]?.[doc.documento_id] ?? '';
    if (!motivo.trim()) return;
    this.selecciones[fila.id] ??= {};
    this.selecciones[fila.id][doc.documento_id] = {
      resultado: 'OBSERVADO', motivo: motivo.trim(),
    };
  }

  puedeRegistrar(fila: Fila): boolean {
    const docs = this.documentos[fila.id];
    const selecciones = this.selecciones[fila.id];
    return !!docs?.length && docs.every(doc => !!selecciones?.[doc.documento_id]);
  }

  registrar(fila: Fila) {
    if (!this.puedeRegistrar(fila)) return;
    const decisiones = this.documentos[fila.id].map(doc => {
      const decision = this.selecciones[fila.id][doc.documento_id];
      return decision.resultado === 'OBSERVADO'
        ? { documento_id: doc.documento_id, version: doc.version,
            resultado: decision.resultado, motivo: decision.motivo }
        : { documento_id: doc.documento_id, version: doc.version,
            resultado: decision.resultado };
    });
    this.api.post(`/auditorias/solicitudes/${fila.id}`, {
      decisiones,
    }).subscribe(() => {
      if (this.documentos[fila.id].some(doc => doc.documento_id === this.vista?.id)) this.cerrarVista();
      delete this.documentos[fila.id];
      delete this.selecciones[fila.id];
      delete this.motivos[fila.id];
      this.filas = this.filas.filter(f => f.id !== fila.id);
      if (this.historialAbierto) this.cargarAprobaciones();
    });
  }
}
