import { Component, OnInit, inject } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { SolicitudService } from '../solicitud.service';

@Component({
  selector: 'app-seguimiento',
  standalone: true,
  template: `
    <div class="stack">
      <header>
        <p class="muted">Paso 3 de 3 · Seguimiento</p>
        <h1>Mi preinscripción</h1>
        <p>Solicitud <strong>{{ numero }}</strong></p>
        <span class="status">{{ etiquetaEstado }}</span>
      </header>
      @if (observados.length) {
        <section>
          <h2>Necesitás corregir estos documentos</h2>
          <p>Reemplazalos y luego reenviá la documentación para una nueva revisión.</p>
          @for (obs of observados; track obs.documento_id) {
            <article><strong>Documento {{ obs.documento_id }}</strong><p>{{ obs.motivo }}</p></article>
          }
          <button type="button" (click)="corregir()">Corregir documentos</button>
        </section>
      } @else {
        <section><h2>Todo en orden</h2><p>No hay observaciones pendientes. Te avisaremos por correo cuando cambie el estado.</p></section>
      }
    </div>
  `,
})
export class SeguimientoComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private service = inject(SolicitudService);
  numero = '';
  estado = '';
  observados: { documento_id: number; motivo: string }[] = [];
  get etiquetaEstado() {
    return this.estado.replaceAll('_', ' ') || 'Cargando…';
  }
  id = Number(this.route.snapshot.paramMap.get('id'));

  ngOnInit() {
    this.service.obtener(this.id).subscribe(sol => {
      this.numero = sol.numero ?? 'Borrador';
      this.estado = sol.estado;
    });
    this.service.observados(this.id).subscribe(items => this.observados = items);
  }

  corregir() {
    this.router.navigate(['/portal/documentos']);
  }
}
