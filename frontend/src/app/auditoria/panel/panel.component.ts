import { Component, OnInit, inject } from '@angular/core';
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

type DecisionLocal = { resultado: 'APROBADO' | 'OBSERVADO'; motivo?: string };

@Component({
  selector: 'app-panel',
  standalone: true,
  template: `
    <h1>Auditoría documental</h1>
    @for (fila of filas; track fila.numero) {
      <article>
        <strong>{{ fila.numero }}</strong> — {{ fila.dni }} — {{ fila.estado }}
        <button (click)="cargarDocumentos(fila)">Auditar</button>
        @if (documentos[fila.id]) {
          <ul>
            @for (doc of documentos[fila.id]; track doc.documento_id) {
              <li>
                Documento {{ doc.documento_id }} v{{ doc.version }} ({{ doc.estado }})
                @for (motivo of doc.observaciones; track motivo) { <em>{{ motivo }}</em> }
                <button (click)="aprobar(fila, doc)">Aprobar</button>
                <button (click)="observar(fila, doc)">Observar</button>
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
  documentos: Record<number, Doc[]> = {};
  selecciones: Record<number, Record<number, DecisionLocal>> = {};

  ngOnInit() {
    this.api.get<Fila[]>('/auditorias/solicitudes')
      .subscribe(filas => this.filas = filas.filter(
        f => f.estado === 'EN_AUDITORIA' || f.estado === 'EN_REAUDITORIA'));
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

  observar(fila: Fila, doc: Doc) {
    const motivo = window.prompt('Motivo de la observación');
    if (!motivo?.trim()) return;
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
      delete this.documentos[fila.id];
      delete this.selecciones[fila.id];
      this.filas = this.filas.filter(f => f.id !== fila.id);
    });
  }
}
