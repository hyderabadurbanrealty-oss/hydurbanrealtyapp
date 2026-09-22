import { Component, ElementRef, HostListener, OnInit, OnDestroy, ViewChild } from '@angular/core';
import { Router, NavigationEnd } from '@angular/router';
import { Observable, Subject } from 'rxjs';
import { takeUntil, filter } from 'rxjs/operators';
import { AuthService, UserProfile } from './services/auth.service';
import { AnalyticsService } from './services/analytics.service';

@Component({
  standalone: false,
  selector: 'app-root',
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.css'],
})
export class AppComponent implements OnInit, OnDestroy {
  title = 'Hyderabad Urban Realty';
  currentRoute = '';
  showMobileMenu = false;
  showUserMenu = false;
  showResaleMenu = false;

  showEnquiryModal = false;

  currentUser$!: Observable<UserProfile | null>;
  isLoggedIn$!: Observable<boolean>;

  @ViewChild('navWrapper', { static: true }) navWrapper!: ElementRef<HTMLElement>;

  private destroy$ = new Subject<void>();

  constructor(
    private router: Router,
    public auth: AuthService,
    private analytics: AnalyticsService,
  ) {}

  ngOnInit(): void {
    this.currentUser$ = this.auth.currentUser$;
    this.isLoggedIn$ = this.auth.isLoggedIn$;

    this.analytics.initGTM();
    this.analytics.trackPageViews();

    this.router.events.pipe(
      filter(e => e instanceof NavigationEnd),
      takeUntil(this.destroy$),
    ).subscribe(event => {
      this.currentRoute = (event as NavigationEnd).urlAfterRedirects;
      this.setMobileMenu(false);
      this.showUserMenu = false;
      this.showResaleMenu = false;
    });
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }

  openEnquiryModal(): void  { this.showEnquiryModal = true; }
  closeEnquiryModal(): void { this.showEnquiryModal = false; }

  @HostListener('document:click', ['$event'])
  onDocumentClick(event: MouseEvent) {
    if (!this.showMobileMenu && !this.showUserMenu) return;
    const target = event.target as HTMLElement;
    if (this.navWrapper && !this.navWrapper.nativeElement.contains(target)) {
      this.setMobileMenu(false);
      this.showUserMenu = false;
      this.showResaleMenu = false;
    }
  }

  toggleMobileMenu() { this.setMobileMenu(!this.showMobileMenu); }
  closeMobileMenu()  { this.setMobileMenu(false); }
  toggleUserMenu()   { this.showUserMenu = !this.showUserMenu; }
  toggleResaleMenu() { this.showResaleMenu = !this.showResaleMenu; this.showUserMenu = false; }
  closeResaleMenu()  { this.showResaleMenu = false; }

  setMobileMenu(open: boolean) {
    this.showMobileMenu = open;
    document.body.style.overflow = open ? 'hidden' : '';
  }

  logout(): void {
    this.showUserMenu = false;
    this.auth.logout().subscribe();
  }

  isLoginOrAdminRoute(): boolean {
    return this.currentRoute.startsWith('/login')          ||
           this.currentRoute.startsWith('/admin')          ||
           this.currentRoute.startsWith('/register')       ||
           this.currentRoute.startsWith('/forgot-password')||
           this.currentRoute.startsWith('/reset-password') ||
           this.currentRoute.startsWith('/verify-email');
  }
}
