import { Injectable, inject } from '@angular/core';
import { ApiService } from '../core/api.service';

export interface Solicitud {
  id: number;
  numero: string | null;
  estado: string;
  version?: number;
}
export interface Convocatoria {
  id: number; nombre: string; anio: number; activa: boolean;
}
export interface Carrera {
  id: number; nombre: string; codigo: string; activa: boolean;
}

@Injectable({ providedIn: 'root' })
export class SolicitudService {
  private api = inject(ApiService);
  convocatorias() {
    return this.api.get<Convocatoria[]>('/catalogos/convocatorias');
  }
  carreras() {
    return this.api.get<Carrera[]>('/catalogos/carreras');
  }

  crear(data: Record<string, unknown>) {
    return this.api.post<Solicitud>('/solicitudes', data);
  }

  obtener(id: number) {
    return this.api.get<Solicitud>(`/solicitudes/${id}`);
  }

  confirmar(id: number, version: number) {
    return this.api.post<{ numero: string; estado: string; version?: number }>(
      `/solicitudes/${id}/confirmar`, { version });
  }

  observados(id: number) {
    return this.api.get<{ documento_id: number; motivo: string }[]>(
      `/solicitudes/${id}/documentos-observados`);
  }

  reenviar(id: number, version: number) {
    return this.api.post<Solicitud>(`/solicitudes/${id}/reenviar`, { version });
  }

  pedirUrlSubida(body: Record<string, unknown>) {
    return this.api.post<{ url: string; documento_id: number; expires_in: number }>(
      '/documentos/upload-url', body);
  }
}
