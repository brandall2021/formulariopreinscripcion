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
  estado: string;
  object_key: string | null;
  observaciones: string[];
}

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
                Documento {{ doc.documento_id }} ({{ doc.estado }})
                @for (motivo of doc.observaciones; track motivo) { <em>{{ motivo }}</em> }
                <button (click)="decidir(fila, doc.documento_id, 'APROBADO')">Aprobar</button>
                <button (click)="observar(fila, doc.documento_id)">Observar</button>
              </li>
            }
          </ul>
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

  ngOnInit() {
    this.api.get<Fila[]>('/auditorias/solicitudes?estado=EN_AUDITORIA')
      .subscribe(filas => this.filas = filas);
  }

  cargarDocumentos(fila: Fila) {
    this.api.get<Doc[]>(`/auditorias/solicitudes/${fila.id}/documentos`)
      .subscribe(docs => this.documentos[fila.id] = docs);
  }

  decidir(fila: Fila, documentoId: number,
          resultado: 'APROBADO' | 'OBSERVADO', motivo?: string) {
    this.api.post(`/auditorias/solicitudes/${fila.id}`, {
      auditor_id: 1,
      decisiones: [{ documento_id: documentoId, resultado, motivo }],
    }).subscribe(() => {
      delete this.documentos[fila.id];
      this.filas = this.filas.filter(f => f.id !== fila.id);
    });
  }

  observar(fila: Fila, documentoId: number) {
    const motivo = window.prompt('Motivo de la observación');
    if (motivo?.trim()) this.decidir(fila, documentoId, 'OBSERVADO', motivo.trim());
  }
}
