import { Injectable, NgZone } from '@angular/core';
import { NavigationEnd, Router } from '@angular/router';
import { BehaviorSubject } from 'rxjs';
import { filter } from 'rxjs/operators';

@Injectable({ providedIn: 'root' })
export class LoadingService {
  private loadingSubject = new BehaviorSubject<boolean>(false);
  private hidingSubject  = new BehaviorSubject<boolean>(false);

  public loading$ = this.loadingSubject.asObservable();
  public hiding$  = this.hidingSubject.asObservable();

  private hideTimer: any = null;

  constructor(private zone: NgZone, private router: Router) {
    // Auto-hide on every NavigationEnd so pages that don't call hide()
    // explicitly (resale, browse, admin, etc.) never get stuck showing loader.
    this.router.events
      .pipe(filter(e => e instanceof NavigationEnd))
      .subscribe(() => this.hide());
  }

  show(): void {
    this.zone.run(() => {
      clearTimeout(this.hideTimer);
      this.hidingSubject.next(false);
      this.loadingSubject.next(true);
    });
  }

  hide(): void {
    this.zone.run(() => {
      this.hidingSubject.next(true);
      clearTimeout(this.hideTimer);
      this.hideTimer = setTimeout(() => {
        this.zone.run(() => {
          this.loadingSubject.next(false);
          this.hidingSubject.next(false);
        });
      }, 260); // match CSS fade-out duration
    });
  }
}
