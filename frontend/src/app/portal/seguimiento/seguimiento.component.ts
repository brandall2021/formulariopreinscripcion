import { Component, DestroyRef, OnInit, inject } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { forkJoin } from 'rxjs';
import { Solicitud, SolicitudService } from '../solicitud.service';

const estados: Record<string, [string, string]> = {
  BORRADOR: ['Borrador', 'Completá la documentación para confirmar tu preinscripción.'],
  RECIBIDA: ['Recibida', 'Recibimos tu preinscripción. La documentación pasará a validación.'],
  EN_VALIDACION: ['En validación', 'Estamos verificando los archivos que enviaste.'],
  EN_AUDITORIA: ['En revisión', 'El equipo de admisión está revisando tu documentación.'],
  OBSERVADA: ['Con observaciones', 'Revisá los motivos indicados en tu documentación.'],
  PENDIENTE_ALUMNO: ['Corrección pendiente', 'Revisá los motivos indicados en tu documentación.'],
  REENVIADA: ['Reenviada', 'Recibimos la documentación corregida.'],
  EN_REAUDITORIA: ['En nueva revisión', 'Estamos revisando la documentación corregida.'],
  DOCUMENTACION_APROBADA: ['Documentación aprobada', 'El equipo de admisión aprobó tus documentos.'],
  FINALIZADA: ['Finalizada', 'El trámite de preinscripción finalizó.'],
  RECHAZADA: ['Rechazada', 'La solicitud de preinscripción fue rechazada.'],
};

@Component({
  selector: 'app-seguimiento',
  standalone: true,
  imports: [RouterLink],
  styles: [`
    :host { display: block; max-width: 800px; margin-inline: auto; }
    .tracking-header { padding: clamp(24px, 5vw, 48px); border-radius: var(--radius);
      background: var(--navy); color: white; }
    .tracking-header h1 { color: inherit; }
    .tracking-header p { margin: 0 0 8px; color: #dcebf6; }
    .state h2 { margin-top: 12px; font-size: 1.45rem; }
    .observations { padding-inline-start: 1.25rem; }
    .observations li { padding-block: 8px; overflow-wrap: anywhere; }
    .button { text-decoration: none; }
  `],
  template: `
    <div class="stack">
      <header class="tracking-header">
        <p>Paso 3 de 3 · Seguimiento</p>
        <h1>Mi preinscripción</h1>
        @if (solicitud?.numero; as numero) { <p>Solicitud <strong>{{ numero }}</strong></p> }
      </header>
      @if (cargando) {
        <p class="card" role="status">Consultando tu preinscripción…</p>
      } @else if (error) {
        <div class="card">
          <p role="alert">{{ error }}</p>
          @if (idValido) {
            <button type="button" (click)="cargar()">Volver a intentar</button>
          }
        </div>
      } @else if (solicitud) {
        <section class="state" aria-labelledby="estado-titulo">
          <span class="status">Estado de la solicitud</span>
          <h2 id="estado-titulo">{{ estado[0] }}</h2>
          <p>{{ estado[1] }}</p>
          @if (solicitud.estado === 'BORRADOR' && puedeRetomar) {
            <a class="button" routerLink="/portal/documentos">Continuar con la documentación</a>
          }
        </section>
        @if (observados.length) {
          <section aria-labelledby="observaciones-titulo">
            <h2 id="observaciones-titulo">Observaciones de documentos</h2>
            <ul class="observations">
              @for (obs of observados; track $index) {
                <li><strong>Documento {{ obs.documento_id }}</strong> · {{ obs.motivo }}</li>
              }
            </ul>
          </section>
        }
      }
    </div>
  `,
})
export class SeguimientoComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private service = inject(SolicitudService);
  private destroyRef = inject(DestroyRef);
  private id = Number(this.route.snapshot.paramMap.get('id'));
  idValido = Number.isSafeInteger(this.id) && this.id > 0;
  solicitud: Solicitud | null = null;
  observados: { documento_id: number; motivo: string }[] = [];
  cargando = false;
  error = '';

  get estado() {
    return estados[this.solicitud?.estado ?? ''] ?? ['Estado sin detalle', 'Volvé a consultar más tarde.'];
  }

  get puedeRetomar() {
    return Number(localStorage.getItem('solicitudId')) === this.id;
  }

  ngOnInit() {
    this.cargar();
  }

  cargar() {
    if (!this.idValido) {
      this.error = 'El enlace de seguimiento tiene un número de solicitud inválido.';
      return;
    }
    this.cargando = true;
    this.error = '';
    forkJoin({
      solicitud: this.service.obtener(this.id),
      observados: this.service.observados(this.id),
    }).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: ({ solicitud, observados }) => {
        this.solicitud = solicitud;
        this.observados = observados;
        this.cargando = false;
      },
      error: ({ status }) => {
        this.error = status === 404
          ? 'No encontramos la solicitud.'
          : 'No pudimos consultar la solicitud. Intentá nuevamente.';
        this.cargando = false;
      },
    });
  }
}
