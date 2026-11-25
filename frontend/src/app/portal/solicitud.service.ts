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
export interface Requisito {
  id: number; convocatoria_id: number; carrera_id: number;
  tipo_ingresante: string; tipo_documento_id: number; obligatorio: boolean;
}
export interface TipoDocumento {
  id: number; codigo: string; nombre: string; descripcion?: string;
  formatos: string; tamano_maximo_bytes: number;
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
  requisitos(convocatoriaId: number, carreraId: number, tipoIngresante: string) {
    return this.api.get<Requisito[]>('/catalogos/requisitos', {
      convocatoria_id: convocatoriaId, carrera_id: carreraId, tipo_ingresante: tipoIngresante,
    });
  }
  tiposDocumentos() {
    return this.api.get<TipoDocumento[]>('/catalogos/tipos-documentos');
  }

  crear(data: Record<string, unknown>) {
    return this.api.post<Solicitud>('/solicitudes', data);
  }

  mia() {
    return this.api.get<Solicitud>('/solicitudes/mia');
  }

  contextoCarga(id: number) {
    return this.api.get<{
      convocatoria_id: number; carrera_id: number; tipo_ingresante: string;
      estado: string; version: number; cargados: number[];
      observaciones: { tipo_documento_id: number; motivo: string }[];
    }>(`/solicitudes/${id}/carga`);
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

  subirDocumento(solicitudId: number, tipoDocumentoId: number, archivo: File) {
    const datos = new FormData();
    datos.set('solicitud_id', String(solicitudId));
    datos.set('tipo_documento_id', String(tipoDocumentoId));
    datos.set('archivo', archivo);
    return this.api.post<{ documento_id: number }>('/documentos/upload', datos);
  }

  pedirUrlSubida(body: Record<string, unknown>) {
    return this.api.post<{ url: string; documento_id: number; expires_in: number }>(
      '/documentos/upload-url', body);
  }
}
