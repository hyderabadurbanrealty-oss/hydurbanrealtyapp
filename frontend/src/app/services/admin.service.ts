import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';

@Injectable({ providedIn: 'root' })
export class AdminService {
  constructor(private http: HttpClient) {}

  // ── Dashboard ──────────────────────────────────────────────────────────────
  getDashboard(): Observable<any> {
    return this.http.get('/api/admin/dashboard');
  }

  // ── User Management ────────────────────────────────────────────────────────
  getUsers(page = 1, pageSize = 50): Observable<any> {
    const params = new HttpParams().set('page', page).set('pageSize', pageSize);
    return this.http.get('/api/admin/users', { params });
  }

  getUserStats(): Observable<any> {
    return this.http.get('/api/admin/users/stats');
  }

  updateUserRole(userId: string, role: string): Observable<any> {
    return this.http.put(`/api/admin/users/${userId}/role`, { role });
  }

  updateUserStatus(userId: string, isActive: boolean): Observable<any> {
    return this.http.put(`/api/admin/users/${userId}/status`, { isActive });
  }

  deleteUser(userId: string): Observable<any> {
    return this.http.delete(`/api/admin/users/${userId}`);
  }

  // ── Property Management ────────────────────────────────────────────────────
  getAdminProperties(): Observable<any> {
    return this.http.get('/api/admin/properties');
  }

  createProperty(data: any): Observable<any> {
    return this.http.post('/api/admin/properties', data);
  }

  updateProperty(id: string, data: any): Observable<any> {
    return this.http.put(`/api/admin/properties/${encodeURIComponent(id)}`, data);
  }

  updatePricing(id: string, pricing: any): Observable<any> {
    return this.http.put(`/api/admin/properties/${encodeURIComponent(id)}/pricing`, pricing);
  }

  deleteProperty(id: string): Observable<any> {
    return this.http.delete(`/api/admin/properties/${encodeURIComponent(id)}`);
  }

  // ── Leads ──────────────────────────────────────────────────────────────────
  getLeads(page = 1, pageSize = 50): Observable<any> {
    const params = new HttpParams().set('page', page).set('pageSize', pageSize);
    return this.http.get('/api/admin/leads', { params });
  }

  deleteLead(id: number): Observable<any> {
    return this.http.delete(`/api/admin/leads/${id}`);
  }

  // ── Schedule Visits ────────────────────────────────────────────────────────
  getVisits(page = 1, pageSize = 50): Observable<any[]> {
    const params = new HttpParams().set('page', page).set('pageSize', pageSize);
    return this.http.get<any[]>('/api/admin/schedule-visits', { params });
  }

  updateVisitStatus(id: number, status: string): Observable<any> {
    return this.http.put(`/api/admin/schedule-visits/${id}/status`, { status });
  }

  deleteVisit(id: number): Observable<any> {
    return this.http.delete(`/api/admin/schedule-visits/${id}`);
  }
}
