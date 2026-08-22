import { Component, ElementRef, HostListener, OnInit, ViewChild } from '@angular/core';
import { Router, NavigationEnd } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { AuthService, UserProfile } from './services/auth.service';

@Component({
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
  enquiryForm = { name: '', mobile: '', interest: '' };
  enquirySubmitting = false;
  enquirySuccess = false;
  enquiryError = '';
  enquiryCaptchaA = 0;
  enquiryCaptchaB = 0;
  enquiryCaptchaAnswer: number | string | null = null;

  get enquiryCaptchaValid(): boolean {
    return this.enquiryCaptchaAnswer !== null &&
           this.enquiryCaptchaAnswer !== '' &&
           +this.enquiryCaptchaAnswer === this.enquiryCaptchaA + this.enquiryCaptchaB;
  }

  openEnquiryModal(): void {
    this.enquirySuccess = false;
    this.enquiryError = '';
    this.enquiryForm = { name: '', mobile: '', interest: '' };
    this.refreshCaptcha();
    this.showEnquiryModal = true;
    document.body.style.overflow = 'hidden';
  }

  closeEnquiryModal(): void {
    this.showEnquiryModal = false;
    document.body.style.overflow = '';
  }

  refreshCaptcha(): void {
    this.enquiryCaptchaA = Math.floor(Math.random() * 9) + 1;
    this.enquiryCaptchaB = Math.floor(Math.random() * 9) + 1;
    this.enquiryCaptchaAnswer = null;
  }

  submitEnquiry(): void {
    this.enquiryError = '';
    if (!this.enquiryForm.name.trim() || !this.enquiryForm.mobile.trim()) {
      this.enquiryError = 'Name and mobile number are required.'; return;
    }
    if (!/^\d{10}$/.test(this.enquiryForm.mobile.trim())) {
      this.enquiryError = 'Enter a valid 10-digit mobile number.'; return;
    }
    if (!this.enquiryCaptchaValid) {
      this.enquiryError = 'Please answer the verification question correctly.'; return;
    }
    this.enquirySubmitting = true;
    this.http.post('/api/submit_lead', {
      name: this.enquiryForm.name.trim(),
      mobile: this.enquiryForm.mobile.trim(),
      areaOfInterest: this.enquiryForm.interest || 'General Enquiry',
      email: '',
      source: 'footer-cta'
    }).subscribe({
      next: () => { this.enquirySubmitting = false; this.enquirySuccess = true; },
      error: () => {
        this.enquirySubmitting = false;
        this.enquiryError = 'Could not submit. Please try again or call us directly.';
      }
    });
  }

  currentUser$!: Observable<UserProfile | null>;
  isLoggedIn$!: Observable<boolean>;

  @ViewChild('navWrapper', { static: true }) navWrapper!: ElementRef<HTMLElement>;

  constructor(private router: Router, public auth: AuthService, private http: HttpClient) {
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
