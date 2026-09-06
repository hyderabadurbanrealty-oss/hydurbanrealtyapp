import { Component, ElementRef, HostListener, OnInit, ViewChild } from '@angular/core';
import { Router, NavigationEnd } from '@angular/router';
import { Observable } from 'rxjs';
import { AuthService, UserProfile } from './services/auth.service';
import { AnalyticsService } from './services/analytics.service';

@Component({
  standalone: false,
  selector: 'app-root',
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.css']
})
export class AppComponent implements OnInit {
  title = 'Hyderabad Urban Realty';
  currentRoute = '';
  showMobileMenu = false;
  showUserMenu = false;

  // ── Enquiry modal ──────────────────────────────────────────────────────────
  showEnquiryModal = false;

  openEnquiryModal(): void {
    this.showEnquiryModal = true;
  }

  closeEnquiryModal(): void {
    this.showEnquiryModal = false;
  }

  currentUser$!: Observable<UserProfile | null>;
  isLoggedIn$!: Observable<boolean>;

  @ViewChild('navWrapper', { static: true }) navWrapper!: ElementRef<HTMLElement>;

  constructor(
    private router: Router, 
    public auth: AuthService,
    private analytics: AnalyticsService
  ) {
    this.router.events.subscribe(event => {
      if (event instanceof NavigationEnd) {
        this.currentRoute = event.urlAfterRedirects;
        this.setMobileMenu(false);
        this.showUserMenu = false;
      }
    });
  }

  ngOnInit(): void {
    this.currentUser$ = this.auth.currentUser$;
    this.isLoggedIn$ = this.auth.isLoggedIn$;
    
    // Initialize Google Tag Manager
    this.analytics.initGTM();
    
    // Track page views on route changes
    this.analytics.trackPageViews();
  }

  @HostListener('document:click', ['$event'])
  onDocumentClick(event: MouseEvent) {
    if (!this.showMobileMenu && !this.showUserMenu) return;
    const target = event.target as HTMLElement;
    if (this.navWrapper && !this.navWrapper.nativeElement.contains(target)) {
      this.setMobileMenu(false);
      this.showUserMenu = false;
    }
  }

  toggleMobileMenu() { this.setMobileMenu(!this.showMobileMenu); }
  closeMobileMenu() { this.setMobileMenu(false); }
  toggleUserMenu() { this.showUserMenu = !this.showUserMenu; }

  setMobileMenu(open: boolean) {
    this.showMobileMenu = open;
    document.body.style.overflow = this.showMobileMenu ? 'hidden' : '';
  }

  logout(): void {
    this.showUserMenu = false;
    this.auth.logout().subscribe();
  }

  isLoginOrAdminRoute(): boolean {
    return this.currentRoute.startsWith('/login') ||
           this.currentRoute.startsWith('/admin') ||
           this.currentRoute.startsWith('/register') ||
           this.currentRoute.startsWith('/forgot-password') ||
           this.currentRoute.startsWith('/reset-password') ||
           this.currentRoute.startsWith('/verify-email');
  }
}
