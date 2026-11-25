import { Component, OnInit, inject } from '@angular/core';
import { ApiService } from '../../core/api.service';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  template: `
    <div class="stack">
      <header>
        <p class="muted">Administración</p>
        <h1>Tablero FACE</h1>
        <p>Una vista rápida del estado de las preinscripciones.</p>
      </header>
      @if (loading) { <p class="card" role="status">Cargando indicadores…</p> }
      @if (error) {
        <p class="error" role="alert">{{ error }}
          <button type="button" (click)="cargar()">Reintentar</button>
        </p>
      }
      @if (!loading && !error) {
        <div class="grid-2">
          <article class="card"><p class="muted">Total</p><h2>{{ resumen.total }}</h2><p>solicitudes registradas</p></article>
          <article class="card"><p class="muted">Correos enviados</p><h2>{{ resumen.notificaciones_enviadas }}</h2><p>notificaciones entregadas</p></article>
          <article class="card"><p class="muted">Correos fallidos</p><h2>{{ resumen.notificaciones_fallidas }}</h2><p>requieren atención</p></article>
          <article class="card"><p class="muted">Estados</p>
            @for (item of estados; track item[0]) {
              <p><span class="status">{{ item[0] }}</span> {{ item[1] }}</p>
            } @empty { <p>No hay solicitudes todavía.</p> }
          </article>
        </div>
      }
    </div>
  `,
})
export class DashboardComponent implements OnInit {
  private api = inject(ApiService);
  resumen = { total: 0, notificaciones_enviadas: 0, notificaciones_fallidas: 0,
              por_estado: {} as Record<string, number> };
  loading = true;
  error = '';
  ngOnInit() {
    this.cargar();
  }
  cargar() {
    this.loading = true; this.error = '';
    this.api.get<typeof this.resumen>('/reportes/resumen')
      .subscribe({
        next: data => { this.resumen = data; this.loading = false; },
        error: () => { this.error = 'No se pudo cargar el tablero.'; this.loading = false; },
      });
  }
  get estados() { return Object.entries(this.resumen.por_estado); }
}
