import { Injectable } from '@angular/core';
import { Meta, Title } from '@angular/platform-browser';
import { Router, NavigationEnd } from '@angular/router';
import { filter } from 'rxjs/operators';

export interface SEOConfig {
  title?: string;
  description?: string;
  keywords?: string;
  image?: string;
  url?: string;
  type?: string;
  author?: string;
  publishedTime?: string;
  modifiedTime?: string;
  structuredData?: any;
}

@Injectable({
  providedIn: 'root'
})
export class SeoService {
  private defaultConfig: SEOConfig = {
    title: 'Hyderabad Urban Realty - Premium Real Estate Properties in Hyderabad',
    description: 'Discover premium residential and commercial properties in Hyderabad. Verified RERA approved projects, transparent information, expert guidance. Your trusted real estate partner.',
    keywords: 'hyderabad real estate, properties in hyderabad, apartments hyderabad, villas hyderabad, RERA approved projects, residential properties, commercial properties, real estate hyderabad',
    image: 'https://www.hyderabadurbanrealty.com/assets/blue-Logo.png',
    url: 'https://www.hyderabadurbanrealty.com',
    type: 'website',
    author: 'Hyderabad Urban Realty'
  };

  constructor(
    private meta: Meta,
    private title: Title,
    private router: Router
  ) {
    // Track route changes for analytics
    this.router.events.pipe(
      filter(event => event instanceof NavigationEnd)
    ).subscribe((event: any) => {
      // Update canonical URL on route change
      this.updateCanonicalUrl(event.urlAfterRedirects);
    });
  }

  /**
   * Update all SEO tags for a page
   */
  updateTags(config: SEOConfig): void {
    const seoConfig = { ...this.defaultConfig, ...config };
    
    // Update title
    if (seoConfig.title) {
      this.title.setTitle(seoConfig.title);
    }

    // Update or add meta tags
    const tags = [
      // Basic meta tags
      { name: 'description', content: seoConfig.description || this.defaultConfig.description },
      { name: 'keywords', content: seoConfig.keywords || this.defaultConfig.keywords },
      { name: 'author', content: seoConfig.author || this.defaultConfig.author },
      { name: 'robots', content: 'index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1' },
      { name: 'googlebot', content: 'index, follow' },
      { name: 'theme-color', content: '#0d3b73' },
      
      // Open Graph tags
      { property: 'og:title', content: seoConfig.title || this.defaultConfig.title },
      { property: 'og:description', content: seoConfig.description || this.defaultConfig.description },
      { property: 'og:image', content: seoConfig.image || this.defaultConfig.image },
      { property: 'og:url', content: seoConfig.url || this.defaultConfig.url },
      { property: 'og:type', content: seoConfig.type || this.defaultConfig.type },
      { property: 'og:site_name', content: 'Hyderabad Urban Realty' },
      { property: 'og:locale', content: 'en_IN' },
      
      // Twitter Card tags
      { name: 'twitter:card', content: 'summary_large_image' },
      { name: 'twitter:title', content: seoConfig.title || this.defaultConfig.title },
      { name: 'twitter:description', content: seoConfig.description || this.defaultConfig.description },
      { name: 'twitter:image', content: seoConfig.image || this.defaultConfig.image },
      { name: 'twitter:site', content: '@HydUrbanRealty' },
      
      // Additional meta tags
      { name: 'format-detection', content: 'telephone=no' },
      { name: 'viewport', content: 'width=device-width, initial-scale=1.0' }
    ];

    // Add article-specific tags if type is article
    if (seoConfig.type === 'article') {
      if (seoConfig.publishedTime) {
        tags.push({ property: 'article:published_time', content: seoConfig.publishedTime });
      }
      if (seoConfig.modifiedTime) {
        tags.push({ property: 'article:modified_time', content: seoConfig.modifiedTime });
      }
      tags.push({ property: 'article:author', content: seoConfig.author || this.defaultConfig.author });
    }

    // Update all meta tags
    tags.forEach(tag => {
      if ('name' in tag && tag.name) {
        this.meta.updateTag(tag as any);
      } else if ('property' in tag && tag.property) {
        this.meta.updateTag(tag as any);
      }
    });

    // Update canonical URL
    if (seoConfig.url) {
      this.updateCanonicalUrl(seoConfig.url);
    }

    // Add structured data if provided
    if (seoConfig.structuredData) {
      this.addStructuredData(seoConfig.structuredData);
    }
  }

  /**
   * Update canonical URL
   */
  private updateCanonicalUrl(url: string): void {
    const fullUrl = url.startsWith('http') ? url : `https://www.hyderabadurbanrealty.com${url}`;
    
    // Remove existing canonical link
    const existingLink = document.querySelector('link[rel="canonical"]');
    if (existingLink) {
      existingLink.setAttribute('href', fullUrl);
    } else {
      // Create new canonical link
      const link = document.createElement('link');
      link.setAttribute('rel', 'canonical');
      link.setAttribute('href', fullUrl);
      document.head.appendChild(link);
    }
  }

  /**
   * Add JSON-LD structured data
   */
  private addStructuredData(data: any): void {
    // Remove existing structured data
    const existingScript = document.querySelector('script[type="application/ld+json"]');
    if (existingScript) {
      existingScript.remove();
    }

    // Add new structured data
    const script = document.createElement('script');
    script.type = 'application/ld+json';
    script.text = JSON.stringify(data);
    document.head.appendChild(script);
  }

  /**
   * Generate property structured data
   */
  generatePropertyStructuredData(property: any): any {
    return {
      '@context': 'https://schema.org',
      '@type': 'RealEstateListing',
      name: property.projectName || property.project_name,
      description: property.description || `${property.projectName} - Premium property in ${property.locality || property.district}`,
      url: `https://www.hyderabadurbanrealty.com/property/${property.projectId || property.project_id}`,
      image: property.thumbnail || property.images?.[0]?.fileUrl,
      address: {
        '@type': 'PostalAddress',
        streetAddress: property.locality,
        addressLocality: property.locality,
        addressRegion: property.district || 'Hyderabad',
        postalCode: property.pinCode || property.pin_code,
        addressCountry: 'IN'
      },
      geo: property.latitude && property.longitude ? {
        '@type': 'GeoCoordinates',
        latitude: property.latitude,
        longitude: property.longitude
      } : undefined,
      offers: {
        '@type': 'Offer',
        priceCurrency: 'INR',
        price: property.price || property.minPrice,
        availability: 'https://schema.org/InStock'
      },
      brand: {
        '@type': 'Brand',
        name: property.developerName || property.developer_name || 'Hyderabad Urban Realty'
      },
      additionalProperty: [
        {
          '@type': 'PropertyValue',
          name: 'RERA Registration',
          value: property.reraRegistrationNumber || property.rera_registration_number || 'Registered'
        },
        {
          '@type': 'PropertyValue',
          name: 'Property Type',
          value: property.propertyType || property.property_type || 'Residential'
        }
      ]
    };
  }

  /**
   * Generate organization structured data
   */
  generateOrganizationStructuredData(): any {
    return {
      '@context': 'https://schema.org',
      '@type': 'RealEstateAgent',
      name: 'Hyderabad Urban Realty',
      url: 'https://www.hyderabadurbanrealty.com',
      logo: 'https://www.hyderabadurbanrealty.com/assets/blue-Logo.png',
      image: 'https://www.hyderabadurbanrealty.com/assets/blue-Logo.png',
      description: 'Premium real estate services in Hyderabad. Verified RERA approved properties, transparent information, and expert guidance.',
      address: {
        '@type': 'PostalAddress',
        addressLocality: 'Hyderabad',
        addressRegion: 'Telangana',
        addressCountry: 'IN'
      },
      contactPoint: {
        '@type': 'ContactPoint',
        telephone: '+91-XXXXXXXXXX',
        contactType: 'Customer Service',
        areaServed: 'IN',
        availableLanguage: ['English', 'Hindi', 'Telugu']
      },
      sameAs: [
        'https://www.facebook.com/hyderabadurbanrealty',
        'https://twitter.com/HydUrbanRealty',
        'https://www.instagram.com/hyderabadurbanrealty'
      ]
    };
  }

  /**
   * Generate breadcrumb structured data
   */
  generateBreadcrumbStructuredData(breadcrumbs: Array<{name: string, url: string}>): any {
    return {
      '@context': 'https://schema.org',
      '@type': 'BreadcrumbList',
      itemListElement: breadcrumbs.map((crumb, index) => ({
        '@type': 'ListItem',
        position: index + 1,
        name: crumb.name,
        item: `https://www.hyderabadurbanrealty.com${crumb.url}`
      }))
    };
  }

  /**
   * Reset to default tags
   */
  resetTags(): void {
    this.updateTags(this.defaultConfig);
  }
}
