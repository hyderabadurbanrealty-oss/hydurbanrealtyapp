import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, of } from 'rxjs';

@Injectable({ providedIn: 'root' })
export class UserDataService {
  constructor(private http: HttpClient) {}

  // ── Favorites ──────────────────────────────────────────────────────────────

  getFavorites(): Observable<any[]> {
    return this.http.get<any[]>('/api/user/favorites');
  }

  addFavorite(projectId: string): Observable<any> {
    return this.http.post('/api/user/favorites', { projectId });
  }

  removeFavorite(projectId: string): Observable<any> {
    return this.http.delete(`/api/user/favorites/${encodeURIComponent(projectId)}`);
  }

  isFavorited(projectId: string): Observable<{ exists: boolean }> {
    return this.http.get<{ exists: boolean }>(`/api/user/favorites/${encodeURIComponent(projectId)}/exists`);
  }

  // ── Saved Properties ───────────────────────────────────────────────────────

  getSavedProperties(): Observable<any[]> {
    return this.http.get<any[]>('/api/user/saved-properties');
  }

  addSavedProperty(projectId: string, notes?: string): Observable<any> {
    return this.http.post('/api/user/saved-properties', { projectId, notes });
  }

  removeSavedProperty(projectId: string): Observable<any> {
    return this.http.delete(`/api/user/saved-properties/${encodeURIComponent(projectId)}`);
  }

  isPropertySaved(projectId: string): Observable<{ exists: boolean }> {
    return this.http.get<{ exists: boolean }>(`/api/user/saved-properties/${encodeURIComponent(projectId)}/exists`);
  }

  // ── Saved Searches ─────────────────────────────────────────────────────────

  getSavedSearches(): Observable<any[]> {
    return this.http.get<any[]>('/api/user/saved-searches');
  }

  addSavedSearch(name: string, filters: object): Observable<any> {
    return this.http.post('/api/user/saved-searches', { name, filters });
  }

  updateSavedSearch(id: string, name?: string, filters?: object): Observable<any> {
    return this.http.put(`/api/user/saved-searches/${id}`, { name, filters });
  }

  deleteSavedSearch(id: string): Observable<any> {
    return this.http.delete(`/api/user/saved-searches/${id}`);
  }

  runSavedSearch(id: string): Observable<any> {
    return this.http.post(`/api/user/saved-searches/${id}/run`, {});
  }

  // ── Comparisons ────────────────────────────────────────────────────────────

  getComparisons(): Observable<any[]> {
    return this.http.get<any[]>('/api/user/comparisons');
  }

  addComparison(projectIds: string[], name?: string): Observable<any> {
    return this.http.post('/api/user/comparisons', { projectIds, name });
  }

  getComparison(id: string): Observable<any> {
    return this.http.get<any>(`/api/user/comparisons/${id}`);
  }

  deleteComparison(id: string): Observable<any> {
    return this.http.delete(`/api/user/comparisons/${id}`);
  }
}
