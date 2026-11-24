import { Injectable, inject } from '@angular/core';
import { ApiService } from '../core/api.service';

export interface Solicitud {
  id: number;
  numero: string | null;
  estado: string;
}

@Injectable({ providedIn: 'root' })
export class SolicitudService {
  private api = inject(ApiService);

  crear(data: Record<string, unknown>) {
    return this.api.post<Solicitud>('/solicitudes', data);
  }

  obtener(id: number) {
    return this.api.get<Solicitud>(`/solicitudes/${id}`);
  }

  confirmar(id: number, version: number) {
    return this.api.post<Solicitud>(`/solicitudes/${id}/confirmar`, { version });
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
