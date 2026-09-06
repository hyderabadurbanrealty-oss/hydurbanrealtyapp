import { Injectable } from '@angular/core';
import { NavigationEnd, Router } from '@angular/router';
import { filter } from 'rxjs/operators';
import { environment } from '../../environments/environment';

declare global {
  interface Window {
    dataLayer: any[];
  }
}

@Injectable({
  providedIn: 'root'
})
export class AnalyticsService {
  private gtmInitialized = false;

  constructor(private router: Router) {
    // Initialize dataLayer
    window.dataLayer = window.dataLayer || [];
  }

  /**
   * Initialize Google Tag Manager
   * Call this once in app initialization
   */
  initGTM(): void {
    if (this.gtmInitialized || !environment.gtmId) {
      return;
    }

    try {
      // GTM script
      const script = document.createElement('script');
      script.innerHTML = `
        (function(w,d,s,l,i){
          w[l]=w[l]||[];
          w[l].push({'gtm.start': new Date().getTime(),event:'gtm.js'});
          var f=d.getElementsByTagName(s)[0],
          j=d.createElement(s),
          dl=l!='dataLayer'?'&l='+l:'';
          j.async=true;
          j.src='https://www.googletagmanager.com/gtm.js?id='+i+dl;
          f.parentNode.insertBefore(j,f);
        })(window,document,'script','dataLayer','${environment.gtmId}');
      `;
      document.head.insertBefore(script, document.head.firstChild);

      // GTM noscript fallback
      const noscript = document.createElement('noscript');
      noscript.innerHTML = `
        <iframe src="https://www.googletagmanager.com/ns.html?id=${environment.gtmId}"
          height="0" width="0" style="display:none;visibility:hidden"></iframe>
      `;
      document.body.insertBefore(noscript, document.body.firstChild);

      this.gtmInitialized = true;
      console.log('GTM initialized:', environment.gtmId);
    } catch (error) {
      console.error('GTM initialization failed:', error);
    }
  }

  /**
   * Track SPA page views on route changes
   */
  trackPageViews(): void {
    this.router.events.pipe(
      filter(event => event instanceof NavigationEnd)
    ).subscribe((event: any) => {
      this.trackPageView(event.urlAfterRedirects);
    });
  }

  /**
   * Push event to dataLayer
   */
  private pushToDataLayer(data: any): void {
    try {
      if (window.dataLayer) {
        window.dataLayer.push(data);
      }
    } catch (error) {
      console.error('DataLayer push failed:', error);
    }
  }

  /**
   * Track generic event
   */
  trackEvent(eventName: string, parameters?: any): void {
    this.pushToDataLayer({
      event: eventName,
      ...parameters
    });
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
  trackPropertyView(params: {
    property_id: string;
    property_type?: string;
    listing_type?: string;
    locality?: string;
    city?: string;
    price_range?: string;
    bedrooms?: string;
  }): void {
    this.pushToDataLayer({
      event: 'property_view',
      ...params
    });
  }

  /**
   * Track property search
   */
  trackPropertySearch(params: {
    search_type?: string;
    locality?: string;
    property_type?: string;
    listing_type?: string;
    bedrooms?: string;
    price_range?: string;
  }): void {
    this.pushToDataLayer({
      event: 'property_search',
      ...params
    });
  }

  /**
   * Track property filter
   */
  trackPropertyFilter(filter_name: string, filter_value: string): void {
    this.pushToDataLayer({
      event: 'property_filter',
      filter_name,
      filter_value
    });
  }

  /**
   * Track favorite add
   */
  trackFavoriteAdd(property_id: string, property_type?: string): void {
    this.pushToDataLayer({
      event: 'favorite_add',
      property_id,
      property_type
    });
  }

  /**
   * Track favorite remove
   */
  trackFavoriteRemove(property_id: string, property_type?: string): void {
    this.pushToDataLayer({
      event: 'favorite_remove',
      property_id,
      property_type
    });
  }

  /**
   * Track comparison add
   */
  trackCompareAdd(property_id: string, property_type?: string): void {
    this.pushToDataLayer({
      event: 'compare_add',
      property_id,
      property_type
    });
  }

  /**
   * Track comparison remove
   */
  trackCompareRemove(property_id: string, property_type?: string): void {
    this.pushToDataLayer({
      event: 'compare_remove',
      property_id,
      property_type
    });
  }

  /**
   * Track enquiry start
   */
  trackEnquiryStart(params: {
    property_id: string;
    property_type?: string;
    source?: string;
  }): void {
    this.pushToDataLayer({
      event: 'enquiry_start',
      ...params
    });
  }

  /**
   * Track enquiry submit
   */
  trackEnquirySubmit(params: {
    property_id: string;
    property_type?: string;
    enquiry_type?: string;
    source?: string;
  }): void {
    this.pushToDataLayer({
      event: 'enquiry_submit',
      ...params
    });
  }

  /**
   * Track builder contact
   */
  trackBuilderContact(params: {
    builder_id?: string;
    property_id: string;
    contact_method: string;
  }): void {
    this.pushToDataLayer({
      event: 'builder_contact',
      ...params
    });
  }

  /**
   * Track seller contact
   */
  trackSellerContact(params: {
    seller_listing_id?: string;
    property_id: string;
    contact_method: string;
  }): void {
    this.pushToDataLayer({
      event: 'seller_contact',
      ...params
    });
  }

  /**
   * Track WhatsApp click
   */
  trackWhatsAppClick(property_id: string, source?: string): void {
    this.pushToDataLayer({
      event: 'whatsapp_click',
      property_id,
      source
    });
  }

  /**
   * Track phone click
   */
  trackPhoneClick(property_id: string, source?: string): void {
    this.pushToDataLayer({
      event: 'phone_click',
      property_id,
      source
    });
  }

  /**
   * Track signup
   */
  trackSignup(signup_method: string): void {
    this.pushToDataLayer({
      event: 'signup',
      signup_method
    });
  }

  /**
   * Track login
   */
  trackLogin(login_method: string): void {
    this.pushToDataLayer({
      event: 'login',
      login_method
    });
  }
}
