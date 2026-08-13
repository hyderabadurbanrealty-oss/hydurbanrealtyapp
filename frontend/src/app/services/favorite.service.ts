import { Injectable } from '@angular/core';
import { BehaviorSubject, Observable, of, forkJoin } from 'rxjs';
import { tap, catchError, switchMap, map } from 'rxjs/operators';
import { Property } from '../map/map.component';
import { AuthService } from './auth.service';
import { UserDataService } from './user-data.service';
import { HttpClient } from '@angular/common/http';

const LOCAL_KEY = 'hur_favorites';

@Injectable({ providedIn: 'root' })
export class FavoriteService {
  private favoritesSubject = new BehaviorSubject<Property[]>(this.loadLocal());

  favorites$ = this.favoritesSubject.asObservable();

  constructor(
    private auth: AuthService,
    private userData: UserDataService,
    private http: HttpClient
  ) {
    this.auth.currentUser$.subscribe(user => {
      if (user) {
        this.syncFromApi();
      } else {
        this.favoritesSubject.next(this.loadLocal());
      }
    });
  }

  private syncFromApi(): void {
    this.userData.getFavorites().pipe(
      catchError(() => of([])),
      switchMap((apiFavs: any[]) => {
        if (!apiFavs.length) {
          this.favoritesSubject.next([]);
          return of([]);
        }
        // Fetch full project details for each favorite
        const requests = apiFavs.map((f: any) => {
          const id = f.projectId ?? f.project_id ?? f.id;
          return this.http.get<any>(`/api/projects/${id}`).pipe(
            catchError(() => of({
              id,
              'Project Name': f.projectName ?? f.name ?? id,
              locality: f.locality,
              district: f.district,
              'Locality': f.locality,
              'District': f.district,
              'Project Status': f.projectStatus,
            }))
          );
        });
        return forkJoin(requests);
      })
    ).subscribe((properties: any[]) => {
      this.favoritesSubject.next(properties as Property[]);
    });
  }

  private loadLocal(): Property[] {
    try {
      const json = localStorage.getItem(LOCAL_KEY);
      if (!json) return [];
      const parsed = JSON.parse(json);
      return Array.isArray(parsed) ? parsed : [];
    } catch { return []; }
  }

  private saveLocal(favs: Property[]): void {
    try { localStorage.setItem(LOCAL_KEY, JSON.stringify(favs)); } catch {}
  }

  getFavorites(): Property[] { return this.favoritesSubject.getValue(); }

  isFavorite(id?: string): boolean {
    if (!id) return false;
    return this.getFavorites().some(p => (p as any).id === id || (p as any).projectId === id);
  }

  /** Toggle and return new isFavorite state */
  toggleFavorite(property: Property): boolean {
    const id = (property as any).id ?? (property as any).projectId;
    if (!id) return false;
    const current = this.getFavorites();
    const alreadyFav = current.some(p => (p as any).id === id || (p as any).projectId === id);

    if (this.auth.isLoggedIn()) {
      if (alreadyFav) {
        this.userData.removeFavorite(id).pipe(catchError(() => of(null))).subscribe();
      } else {
        this.userData.addFavorite(id).pipe(catchError(() => of(null))).subscribe();
      }
    }

    const updated = alreadyFav
      ? current.filter(p => (p as any).id !== id && (p as any).projectId !== id)
      : [...current, property];

    this.favoritesSubject.next(updated);
    if (!this.auth.isLoggedIn()) this.saveLocal(updated);
    return !alreadyFav;
  }

  clearFavorites(): void {
    if (this.auth.isLoggedIn()) {
      // Clear via API — remove each individually (API has no bulk-clear)
      this.getFavorites().forEach(p => {
        const id = (p as any).id ?? (p as any).projectId;
        if (id) this.userData.removeFavorite(id).pipe(catchError(() => of(null))).subscribe();
      });
    }
    this.favoritesSubject.next([]);
    this.saveLocal([]);
  }
}
