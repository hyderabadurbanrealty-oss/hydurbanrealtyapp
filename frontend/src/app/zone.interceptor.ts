import { Injectable, NgZone } from '@angular/core';
import { HttpEvent, HttpHandler, HttpInterceptor, HttpRequest } from '@angular/common/http';
import { Observable } from 'rxjs';

/**
 * Forces every HTTP response to be emitted inside NgZone, so Angular's change
 * detection always runs after data arrives — even if a third-party script
 * (e.g. Google Identity Services, MapLibre) interferes with zone.js's
 * automatic XHR/fetch task tracking.
 */
@Injectable()
export class ZoneInterceptor implements HttpInterceptor {
  constructor(private zone: NgZone) {}

  intercept(req: HttpRequest<any>, next: HttpHandler): Observable<HttpEvent<any>> {
    return new Observable(observer => {
      const sub = next.handle(req).subscribe({
        next: event => this.zone.run(() => observer.next(event)),
        error: err => this.zone.run(() => observer.error(err)),
        complete: () => this.zone.run(() => observer.complete())
      });
      return () => sub.unsubscribe();
    });
  }
}
