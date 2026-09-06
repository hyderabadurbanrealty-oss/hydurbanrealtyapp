import { Injectable } from '@angular/core';
import { NavigationEnd, Router } from '@angular/router';
import { filter } from 'rxjs/operators';

declare global {
  interface Window {
    dataLayer: any[];
    gtag: (...args: any[]) => void;
  }
}

export interface PropertyViewEvent {
  property_id: string;
  property_type?: string;
  listing_type?: string;
  locality?: string;
  city?: string;
  price_range?: string;
  bedrooms?: number;
}

export interface PropertySearchEvent {
  search_type?: string;
  locality?: string;
  property_type?: string;
  listing_type?: string;
  bedrooms?: number;
  price_range?: string;
}

export interface PropertyFilterEvent {
  filter_name: string;
  filter_value: string;
}

export interface FavoriteEvent {
  property_id: string;
  property_type?: string;
}

export interface CompareEvent {
  property_id: string;
  property_type?: string;
}

export interface EnquiryStartEvent {
  property_id: string;
  property_type?: string;
  source?: string;
}

export interface EnquirySubmitEvent {
  property_id: string;
  property_type?: string;
  enquiry_type?: string;
  source?: string;
}

export interface BuilderContactEvent {
  builder_id: string;
  property_id?: string;
  contact_method: string;
}

export interface SellerContactEvent {
  seller_listing_id: string;
  property_id?: string;
  contact_method: string;
}

export interface ContactClickEvent {
  property_id: string;
  source?: string;
}

export interface AuthEvent {
  method: string;
}

@Injectable({
  providedIn: 'root'
})
export class AnalyticsService {
  private isInitialized = false;
  private lastTrackedUrl: string | null = null;

  constructor(private router: Router) {
    this.initializeDataLayer();
  }

  /**
   * Initialize dataLayer if not already present
   */
  private initializeDataLayer(): void {
    try {
      if (typeof window !== 'undefined') {
        window.dataLayer = window.dataLayer || [];
        this.isInitialized = true;
      }
    } catch (error) {
      console.warn('Analytics: Failed to initialize dataLayer', error);
    }
  }

  /**
   * Safely push event to dataLayer
   */
  private pushToDataLayer(event: any): void {
    try {
      if (this.isInitialized && typeof window !== 'undefined' && window.dataLayer) {
        window.dataLayer.push(event);
      }
    } catch (error) {
      console.warn('Analytics: Failed to push event', error);
    }
  }

  /**
   * Initialize Google Tag Manager
   * Call this once in app.component.ts ngOnInit
   */
  initGTM(): void {
    // GTM is initialized via index.html script tags
    // This method is kept for consistency but GTM loads automatically
    this.initializeDataLayer();
  }

  /**
   * Initialize SPA page view tracking
   * Call this once in app.component.ts ngOnInit
   */
  trackPageViews(): void {
    try {
      this.router.events
        .pipe(filter(event => event instanceof NavigationEnd))
        .subscribe((event: NavigationEnd) => {
          // Prevent duplicate tracking
          if (event.urlAfterRedirects !== this.lastTrackedUrl) {
            this.trackPageView(event.urlAfterRedirects);
            this.lastTrackedUrl = event.urlAfterRedirects;
          }
        });
    } catch (error) {
      console.warn('Analytics: Failed to initialize page view tracking', error);
    }
  }

  /**
   * Legacy method name - use trackPageViews() instead
   * @deprecated
   */
  initPageViewTracking(): void {
    this.trackPageViews();
  }

  /**
   * Track page view
   */
  trackPageView(path: string): void {
    this.pushToDataLayer({
      event: 'page_view',
      page_path: path,
      page_title: document.title
    });
  }

  /**
   * Track property view
   */
  trackPropertyView(data: PropertyViewEvent): void {
    this.pushToDataLayer({
      event: 'property_view',
      ...data
    });
  }

  /**
   * Track property search
   */
  trackPropertySearch(data: PropertySearchEvent): void {
    this.pushToDataLayer({
      event: 'property_search',
      ...data
    });
  }

  /**
   * Track property filter
   */
  trackPropertyFilter(data: PropertyFilterEvent): void {
    this.pushToDataLayer({
      event: 'property_filter',
      ...data
    });
  }

  /**
   * Track adding favorite
   */
  trackFavoriteAdd(data: FavoriteEvent): void {
    this.pushToDataLayer({
      event: 'favorite_add',
      ...data
    });
  }

  /**
   * Track removing favorite
   */
  trackFavoriteRemove(data: FavoriteEvent): void {
    this.pushToDataLayer({
      event: 'favorite_remove',
      ...data
    });
  }

  /**
   * Track adding to comparison
   */
  trackCompareAdd(data: CompareEvent): void {
    this.pushToDataLayer({
      event: 'compare_add',
      ...data
    });
  }

  /**
   * Track removing from comparison
   */
  trackCompareRemove(data: CompareEvent): void {
    this.pushToDataLayer({
      event: 'compare_remove',
      ...data
    });
  }

  /**
   * Track enquiry start
   */
  trackEnquiryStart(data: EnquiryStartEvent): void {
    this.pushToDataLayer({
      event: 'enquiry_start',
      ...data
    });
  }

  /**
   * Track enquiry submit
   */
  trackEnquirySubmit(data: EnquirySubmitEvent): void {
    this.pushToDataLayer({
      event: 'enquiry_submit',
      ...data
    });
  }

  /**
   * Track builder contact
   */
  trackBuilderContact(data: BuilderContactEvent): void {
    this.pushToDataLayer({
      event: 'builder_contact',
      ...data
    });
  }

  /**
   * Track seller contact
   */
  trackSellerContact(data: SellerContactEvent): void {
    this.pushToDataLayer({
      event: 'seller_contact',
      ...data
    });
  }

  /**
   * Track WhatsApp click
   */
  trackWhatsAppClick(data: ContactClickEvent): void {
    this.pushToDataLayer({
      event: 'whatsapp_click',
      ...data
    });
  }

  /**
   * Track phone click
   */
  trackPhoneClick(data: ContactClickEvent): void {
    this.pushToDataLayer({
      event: 'phone_click',
      ...data
    });
  }

  /**
   * Track signup
   */
  trackSignup(data: AuthEvent): void {
    this.pushToDataLayer({
      event: 'signup',
      signup_method: data.method
    });
  }

  /**
   * Track login
   */
  trackLogin(data: AuthEvent): void {
    this.pushToDataLayer({
      event: 'login',
      login_method: data.method
    });
  }

  /**
   * Generic event tracking
   */
  trackEvent(eventName: string, parameters?: Record<string, any>): void {
    this.pushToDataLayer({
      event: eventName,
      ...parameters
    });
  }
}
