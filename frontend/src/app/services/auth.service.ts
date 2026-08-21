import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { BehaviorSubject, Observable, throwError } from 'rxjs';
import { tap, catchError, map, timeout } from 'rxjs/operators';
import { environment } from '../../environments/environment';

const API = environment.apiUrl;

export interface UserProfile {
  id: string;
  fullName: string;
  email: string;
  mobile?: string;
  avatarUrl?: string;
  isVerified: boolean;
  createdAt: string;
  role?: string;
}

export interface AuthResponse {
  accessToken: string;
  refreshToken: string;
  expiresAt: string;
  user: UserProfile;
}

const ACCESS_TOKEN_KEY = 'authToken';
const REFRESH_TOKEN_KEY = 'refreshToken';
const USER_KEY = 'currentUser';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private _currentUser = new BehaviorSubject<UserProfile | null>(this.loadUser());

  currentUser$ = this._currentUser.asObservable();
  isLoggedIn$ = this._currentUser.pipe(map(u => u !== null));
  isAdmin$ = this._currentUser.pipe(map(u => u?.role === 'admin'));

  constructor(private http: HttpClient, private router: Router) {
    // On startup, if we have a token but no cached user, fetch profile
    const token = this.getAccessToken();
    const user = this.loadUser();
    if (token && !user) {
      this.fetchAndCacheProfile().subscribe({ error: () => this.clearSession() });
    }
  }

  // ── Token helpers ──────────────────────────────────────────────────────────

  getAccessToken(): string | null {
    return localStorage.getItem(ACCESS_TOKEN_KEY);
  }

  getRefreshToken(): string | null {
    return localStorage.getItem(REFRESH_TOKEN_KEY);
  }

  isLoggedIn(): boolean {
    return !!this.getAccessToken();
  }

  getCurrentUser(): UserProfile | null {
    return this._currentUser.getValue();
  }

  isAdmin(): boolean {
    return this.getCurrentUser()?.role === 'admin';
  }

  private loadUser(): UserProfile | null {
    try {
      const json = localStorage.getItem(USER_KEY);
      return json ? JSON.parse(json) : null;
    } catch {
      return null;
    }
  }

  private saveSession(resp: AuthResponse): void {
    localStorage.setItem(ACCESS_TOKEN_KEY, resp.accessToken);
    localStorage.setItem(REFRESH_TOKEN_KEY, resp.refreshToken);
    localStorage.setItem(USER_KEY, JSON.stringify(resp.user));
    this._currentUser.next(resp.user);
  }

  clearSession(): void {
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    // Keep isAdmin legacy key clean too
    localStorage.removeItem('isAdmin');
    this._currentUser.next(null);
  }

  // ── Auth API calls ─────────────────────────────────────────────────────────

  register(fullName: string, email: string, password: string, mobile?: string): Observable<any> {
    return this.http.post(`${API}/auth/register`, { fullName, email, password, mobile })
      .pipe(timeout(30000));
  }

  login(email: string, password: string, deviceInfo?: string): Observable<AuthResponse> {
    return this.http.post<AuthResponse>(`${API}/auth/login`, { email, password, deviceInfo }).pipe(
      timeout(30000),
      tap(resp => {
        this.saveSession(resp);
        if (resp.user.role === 'admin') {
          localStorage.setItem('isAdmin', 'true');
          localStorage.setItem('authToken', resp.accessToken);
        }
      })
    );
  }

  loginWithGoogle(idToken: string): Observable<AuthResponse> {
    return this.http.post<AuthResponse>(`${API}/auth/google-login`, { idToken }).pipe(
      timeout(30000),
      tap(resp => {
        this.saveSession(resp);
        if (resp.user.role === 'admin') {
          localStorage.setItem('isAdmin', 'true');
          localStorage.setItem('authToken', resp.accessToken);
        }
      })
    );
  }

  logout(): Observable<any> {
    const refreshToken = this.getRefreshToken();
    const req = refreshToken
      ? this.http.post(`${API}/auth/logout`, { refreshToken })
      : new Observable(obs => { obs.next({}); obs.complete(); });
    return req.pipe(
      tap(() => { this.clearSession(); this.router.navigate(['/']); }),
      catchError(err => { this.clearSession(); this.router.navigate(['/']); return throwError(() => err); })
    );
  }

  refreshToken(): Observable<AuthResponse> {
    const refreshToken = this.getRefreshToken();
    if (!refreshToken) return throwError(() => new Error('No refresh token'));
    return this.http.post<AuthResponse>(`${API}/auth/refresh`, { refreshToken }).pipe(
      timeout(30000),
      tap(resp => this.saveSession(resp)),
      catchError(err => { this.clearSession(); return throwError(() => err); })
    );
  }

  forgotPassword(email: string): Observable<any> {
    return this.http.post(`${API}/auth/forgot-password`, { email }).pipe(timeout(30000));
  }

  resetPassword(token: string, newPassword: string): Observable<any> {
    return this.http.post(`${API}/auth/reset-password`, { token, newPassword }).pipe(timeout(30000));
  }

  verifyEmail(token: string): Observable<any> {
    return this.http.post(`${API}/auth/verify-email`, { token }).pipe(timeout(30000));
  }

  resendVerification(email: string): Observable<any> {
    return this.http.post(`${API}/auth/resend-verification`, { email }).pipe(timeout(30000));
  }

  // ── Profile API calls ──────────────────────────────────────────────────────

  getProfile(): Observable<UserProfile> {
    return this.http.get<UserProfile>(`${API}/user/profile`).pipe(
      tap(user => {
        localStorage.setItem(USER_KEY, JSON.stringify(user));
        this._currentUser.next(user);
      })
    );
  }

  updateProfile(fullName?: string, mobile?: string, avatarUrl?: string): Observable<UserProfile> {
    return this.http.put<UserProfile>(`${API}/user/profile`, { fullName, mobile, avatarUrl }).pipe(
      tap(user => {
        localStorage.setItem(USER_KEY, JSON.stringify(user));
        this._currentUser.next(user);
      })
    );
  }

  changePassword(currentPassword: string, newPassword: string): Observable<any> {
    return this.http.put(`${API}/user/change-password`, { currentPassword, newPassword });
  }

  deleteAccount(): Observable<any> {
    return this.http.delete(`${API}/user/account`).pipe(
      tap(() => this.clearSession())
    );
  }

  private fetchAndCacheProfile(): Observable<UserProfile> {
    return this.getProfile();
  }
}
