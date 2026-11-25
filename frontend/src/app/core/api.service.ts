import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { environment } from '../../environments/environment';

@Injectable({ providedIn: 'root' })
export class ApiService {
  private http = inject(HttpClient);
  private base = environment.apiUrl;

  get<T>(path: string, params?: Record<string, string | number>) {
    let query = new HttpParams();
    if (params) Object.entries(params).forEach(([k, v]) => query = query.set(k, v));
    return this.http.get<T>(`${this.base}${path}`, { params: query });
  }

  descargar(path: string) {
    return this.http.get(`${this.base}${path}`, { responseType: 'blob' });
  }

  post<T>(path: string, body: unknown) {
    return this.http.post<T>(`${this.base}${path}`, body);
  }
}
