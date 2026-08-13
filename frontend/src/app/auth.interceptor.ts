import { Injectable } from '@angular/core';
import {
  HttpEvent, HttpInterceptor, HttpHandler, HttpRequest,
  HttpErrorResponse
} from '@angular/common/http';
import { Observable, throwError, BehaviorSubject } from 'rxjs';
import { catchError, filter, switchMap, take } from 'rxjs/operators';
import { AuthService } from './services/auth.service';

@Injectable()
export class AuthInterceptor implements HttpInterceptor {
  private isRefreshing = false;
  private refreshSubject = new BehaviorSubject<string | null>(null);

  constructor(private auth: AuthService) {}

  intercept(req: HttpRequest<any>, next: HttpHandler): Observable<HttpEvent<any>> {
    // Skip auth endpoints — avoid refresh loops
    if (this.isAuthUrl(req.url)) return next.handle(req);

    const token = this.auth.getAccessToken();
    const cloned = token ? this.addToken(req, token) : req;

    return next.handle(cloned).pipe(
      catchError((error: HttpErrorResponse) => {
        if (error.status === 401 && !this.isAuthUrl(req.url)) {
          return this.handle401(req, next);
        }
        return throwError(() => error);
      })
    );
  }

  private handle401(req: HttpRequest<any>, next: HttpHandler): Observable<HttpEvent<any>> {
    if (this.isRefreshing) {
      // Wait for the refresh to complete, then retry
      return this.refreshSubject.pipe(
        filter(t => t !== null),
        take(1),
        switchMap(token => next.handle(this.addToken(req, token!)))
      );
    }

    this.isRefreshing = true;
    this.refreshSubject.next(null);

    return this.auth.refreshToken().pipe(
      switchMap(resp => {
        this.isRefreshing = false;
        this.refreshSubject.next(resp.accessToken);
        return next.handle(this.addToken(req, resp.accessToken));
      }),
      catchError(err => {
        this.isRefreshing = false;
        this.auth.clearSession();
        return throwError(() => err);
      })
    );
  }

  private addToken(req: HttpRequest<any>, token: string): HttpRequest<any> {
    return req.clone({ headers: req.headers.set('Authorization', `Bearer ${token}`) });
  }

  private isAuthUrl(url: string): boolean {
    return (
      url.includes('/api/auth/login') ||
      url.includes('/api/auth/register') ||
      url.includes('/api/auth/refresh') ||
      url.includes('/api/auth/forgot-password') ||
      url.includes('/api/auth/reset-password') ||
      url.includes('/api/auth/verify-email') ||
      url.includes('/api/auth/resend-verification')
    );
  }
}
