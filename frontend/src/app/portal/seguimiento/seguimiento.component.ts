import { Component, OnInit, inject } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { SolicitudService } from '../solicitud.service';

@Component({
  selector: 'app-seguimiento',
  standalone: true,
  template: `
    <h1>Mi preinscripción</h1>
    <p>Solicitud: {{ numero }}</p>
    <p>Estado: {{ estado }}</p>
    @for (obs of observados; track obs.documento_id) {
      <article>Documento {{ obs.documento_id }}: {{ obs.motivo }}</article>
    }
    <button (click)="corregir()">Corregir documentos</button>
  `,
})
export class SeguimientoComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private service = inject(SolicitudService);
  numero = '';
  estado = '';
  observados: { documento_id: number; motivo: string }[] = [];
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
