import { Injectable } from '@angular/core';
import { BehaviorSubject } from 'rxjs';

@Injectable({
  providedIn: 'root'
})
export class LoadingService {
  private loadingSubject = new BehaviorSubject<boolean>(false);
  private hidingSubject = new BehaviorSubject<boolean>(false);
  public loading$ = this.loadingSubject.asObservable();
  public hiding$ = this.hidingSubject.asObservable();

  show() {
    this.hidingSubject.next(false);
    this.loadingSubject.next(true);
  }

  hide() {
    // Trigger fade-out animation first
    this.hidingSubject.next(true);
    // Then remove from DOM after animation completes
    setTimeout(() => {
      this.loadingSubject.next(false);
      this.hidingSubject.next(false);
    }, 500); // Match fadeOut animation duration
  }
}
