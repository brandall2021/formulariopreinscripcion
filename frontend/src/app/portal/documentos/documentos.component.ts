import { Component, inject } from '@angular/core';
import { Router } from '@angular/router';
import { SolicitudService } from '../solicitud.service';
import { sha256 } from './checksum';

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
    <h1>Documentación requerida</h1>
    @for (req of requisitos; track req.id) {
      <section>
        <h2>{{ req.nombre }}</h2>
        <input type="file" accept=".pdf,.jpg,.jpeg,.png"
               (change)="subir(req.id, $event)">
      </section>
    } @empty { <p>Sin requisitos</p> }
  `,
})
export class DocumentosComponent {
  private service = inject(SolicitudService);
  private router = inject(Router);
  requisitos = REQUISITOS;
  solicitudId = Number(localStorage.getItem('solicitudId') ?? 0);

  async subir(tipoDocumentoId: number, event: Event) {
    const archivo = (event.target as HTMLInputElement).files?.[0];
    if (!archivo) return;
    const checksum = await sha256(archivo);
    this.service.pedirUrlSubida({
      solicitud_id: this.solicitudId,
      tipo_documento_id: tipoDocumentoId,
      filename: archivo.name,
      content_type: archivo.type,
      size: archivo.size,
      checksum,
    }).subscribe(({ url }) => {
      fetch(url, { method: 'PUT', body: archivo,
                   headers: { 'Content-Type': archivo.type } });
    });
  }
}
