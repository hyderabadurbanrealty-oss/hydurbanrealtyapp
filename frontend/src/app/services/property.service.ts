import { Injectable } from '@angular/core';
import { Property } from '../map/map.component';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { map } from 'rxjs/operators';

@Injectable({ providedIn: 'root' })
export class PropertyService {
  constructor(private http: HttpClient) {}

  login(username: string, password: string) {
    return this.http.post('/api/login', { username, password });
  }

  logout() {
    return this.http.post('/api/logout', {});
  }

  getLeads(): Observable<any> {
    return this.http.get('/api/leads');
  }

  fetchProjectNames(): Observable<any> {
    return this.http.post('/api/fetch_project_names', {});
  }

  scrapeProject(project_name: string): Observable<any> {
    return this.http.post('/api/scrape_project', { project_name });
  }

  bulkScrape(start_idx: number = 0): Observable<any> {
    return this.http.post('/api/bulk_scrape', { start_idx });
  }

  getProperties(): Observable<Property[]> {
    return this.http.get<Property[]>('/api/projects');
  }

  getPropertyById(id: string): Observable<any> {
    // Use dedicated endpoint for full project details
    return this.http.get<any>(`/api/projects/${id}`);
  }

  updateProject(id: string, data: any): Observable<any> {
    return this.http.put(`/api/projects/${id}`, data);
  }

  updatePricing(id: string, pricing: any): Observable<any> {
    return this.http.put(`/api/projects/${id}/pricing`, pricing);
  }

  getPriceHistory(id: string): Observable<any[]> {
    return this.http.get<any[]>(`/api/projects/${id}/price-history`);
  }

  getFloorPlans(id: string): Observable<any[]> {
    return this.http.get<any[]>(`/api/projects/${encodeURIComponent(id)}/floor-plans`);
  }

  deleteScrapedFloorPlanPage(projectId: string, filename: string): Observable<any> {
    return this.http.delete(`/api/projects/${encodeURIComponent(projectId)}/floor-plans/${encodeURIComponent(filename)}`);
  }

  getReviews(id: string): Observable<any[]> {
    return this.http.get<any[]>(`/api/projects/${id}/reviews`);
  }

  uploadMedia(id: string, formData: FormData): Observable<any> {
    return new Observable(observer => {
      const xhr = new XMLHttpRequest();
      
      xhr.upload.addEventListener('progress', (e) => {
        if (e.lengthComputable) {
          const progress = Math.round((e.loaded / e.total) * 100);
          observer.next({ type: 'progress', progress });
        }
      });
      
      xhr.addEventListener('load', () => {
        if (xhr.status === 200) {
          observer.next({ type: 'response', body: JSON.parse(xhr.responseText) });
          observer.complete();
        } else {
          observer.error({ error: JSON.parse(xhr.responseText) });
        }
      });
      
      xhr.addEventListener('error', () => {
        observer.error({ error: { message: 'Upload failed' } });
      });
      
      xhr.open('POST', `/api/projects/${id}/media`);
      xhr.send(formData);
    });
  }

  getNeighborhoodData(id: string, refresh: boolean = false, saveToFile: boolean = false): Observable<any> {
    const params: any = {};
    if (refresh) params.refresh = 'true';
    if (saveToFile) params.save = 'true';
    
    return this.http.get<any>(`/api/projects/${id}/neighborhood-data`, { params });
  }

  submitLead(leadData: any): Observable<any> {
    return this.http.post('/api/submit_lead', leadData);
  }

  checkUnlockStatus(deviceFingerprint: string): Observable<any> {
    return this.http.get(`/api/check_unlock?fingerprint=${deviceFingerprint}`);
  }

  deleteProperty(id: string): Observable<any> {
    return this.http.delete(`/api/projects/${id}`);
  }

  createProperty(projectData: any): Observable<any> {
    return this.http.post('/api/projects', projectData);
  }

  deleteLead(index: number): Observable<any> {
    return this.http.delete(`/api/leads/${index}`);
  }

  getScrapePreferences(): Observable<any> {
    return this.http.get('/api/scrape-preferences');
  }

  saveScrapePreferences(prefs: { pincodes: string[]; igrs_username?: string; igrs_password?: string }): Observable<any> {
    return this.http.post('/api/scrape-preferences', prefs);
  }

  // ── SRO Transaction Data ──────────────────────────────────────────────────

  getSroCityAggregate(): Observable<Record<string, { avg_price_sqft: number; total_volume: number; count: number }>> {
    return this.http.get<any>('/api/sro/aggregate/city');
  }

  getSroLocalityAggregate(locality?: string): Observable<any> {
    const params = locality ? `?locality=${encodeURIComponent(locality)}` : '';
    return this.http.get<any>(`/api/sro/aggregate/locality${params}`);
  }

  getSroPriceRank(quarter?: string, top = 10): Observable<{ quarter: string; rank: any[] }> {
    let url = `/api/sro/rank/price?top=${top}`;
    if (quarter) url += `&quarter=${encodeURIComponent(quarter)}`;
    return this.http.get<any>(url);
  }

  getSroVolumeRank(quarter?: string, top = 10): Observable<{ quarter: string; rank: any[] }> {
    let url = `/api/sro/rank/volume?top=${top}`;
    if (quarter) url += `&quarter=${encodeURIComponent(quarter)}`;
    return this.http.get<any>(url);
  }

  getSroScrapeStatus(): Observable<any> {
    return this.http.get<any>('/api/sro/scrape/status');
  }

  startSroScrape(options?: { districts?: string[]; start_year?: number; end_year?: number }): Observable<any> {
    return this.http.post('/api/sro/scrape', options || {});
  }

  // ── Ready Reckoner (Unit Rate) Scraping ───────────────────────────────────

  getRrScrapeStatus(): Observable<any> {
    return this.http.get<any>('/api/rr_scrape/status');
  }

  startRrScrape(pincodes?: string[]): Observable<any> {
    return this.http.post('/api/rr_scrape', pincodes ? { pincodes } : {});
  }

  stopRrScrape(): Observable<any> {
    return this.http.post('/api/rr_scrape/stop', {});
  }

  getUnitRates(filters?: { district?: string; mandal?: string; locality?: string }): Observable<any> {
    const params = new URLSearchParams();
    if (filters?.district) params.set('district', filters.district);
    if (filters?.mandal)   params.set('mandal',   filters.mandal);
    if (filters?.locality) params.set('locality', filters.locality);
    const qs = params.toString();
    return this.http.get<any>(`/api/unit_rates${qs ? '?' + qs : ''}`);
  }

  getUnitRatesSummary(): Observable<any[]> {
    return this.http.get<any[]>('/api/unit_rates/summary');
  }

  getSroProjectTrend(projectName: string): Observable<any> {
    return this.http.get<any>(`/api/sro/project/trend?name=${encodeURIComponent(projectName)}`);
  }

  getSroProjectUnits(projectName: string): Observable<any> {
    return this.http.get<any>(`/api/sro/project/units?name=${encodeURIComponent(projectName)}`);
  }

  addReview(id: string, review: any): Observable<any> {
    return this.http.post(`/api/projects/${id}/reviews`, review);
  }

  scheduleVisit(visitData: any): Observable<any> {
    return this.http.post('/api/schedule-visit', visitData);
  }

  downloadDocument(projectId: string, mediaId: string): Observable<Blob> {
    return this.http.get(
      `/api/projects/${encodeURIComponent(projectId)}/media/${mediaId}/download`,
      { responseType: 'blob' }
    );
  }
}
