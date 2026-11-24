import { Component, OnInit, inject } from '@angular/core';
import { ApiService } from '../../core/api.service';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  template: `
    <h1>Tablero FACE</h1>
    <p>Total: {{ resumen.total }}</p>
    <p>Correos enviados: {{ resumen.notificaciones_enviadas }}</p>
    <p>Correos fallidos: {{ resumen.notificaciones_fallidas }}</p>
  `,
})
export class DashboardComponent implements OnInit {
  private api = inject(ApiService);
  resumen = { total: 0, notificaciones_enviadas: 0, notificaciones_fallidas: 0,
              por_estado: {} as Record<string, number> };
  ngOnInit() {
    this.api.get<typeof this.resumen>('/reportes/resumen')
      .subscribe(data => this.resumen = data);
  }
}
