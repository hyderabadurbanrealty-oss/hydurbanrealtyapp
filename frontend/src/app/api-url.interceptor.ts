import { Injectable } from '@angular/core';
import { HttpInterceptor, HttpRequest, HttpHandler, HttpEvent } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../environments/environment';

/**
 * In production, all relative /api/* calls are prepended with the API base URL
 * (e.g. https://hydurban.onrender.com).
 * In development, the Angular proxy (proxy.conf.json) handles /api/* → localhost.
 */
@Injectable()
export class ApiUrlInterceptor implements HttpInterceptor {
  intercept(req: HttpRequest<any>, next: HttpHandler): Observable<HttpEvent<any>> {
    // Only rewrite relative /api/ calls — leave external URLs untouched
    if (environment.production && req.url.startsWith('/api/')) {
      const apiBase = environment.apiUrl.replace(/\/api\/?$/, ''); // strip trailing /api
      const rewritten = req.clone({ url: `${apiBase}${req.url}` });
      return next.handle(rewritten);
    }
    return next.handle(req);
  }
}
