import { Component, OnInit } from '@angular/core';
import { SeoService } from '../services/seo.service';

@Component({
  standalone: false,
  selector: 'app-about',
  templateUrl: './about.component.html',
  styleUrls: ['./about.component.css']
})
export class AboutComponent implements OnInit {
  showEnquiryModal = false;

  constructor(private seoService: SeoService) {}

  ngOnInit(): void {
    // Set SEO meta tags for About page
    this.seoService.updateTags({
      title: 'About Us - Hyderabad Urban Realty | Your Trusted Real Estate Partner',
      description: 'Learn about Hyderabad Urban Realty - your trusted partner for premium real estate in Hyderabad. We provide verified RERA approved properties with transparent information, expert guidance, and comprehensive property insights. Discover our mission, values, and commitment to helping you find your dream property.',
      keywords: 'about hyderabad urban realty, real estate company hyderabad, property consultants hyderabad, RERA verified properties, trusted real estate partner, property expertise hyderabad, real estate services',
      url: 'https://www.hyderabadurbanrealty.com/about',
      image: 'https://www.hyderabadurbanrealty.com/assets/blue-Logo.png',
      type: 'website',
      structuredData: {
        '@context': 'https://schema.org',
        '@type': 'AboutPage',
        name: 'About Hyderabad Urban Realty',
        description: 'Learn about Hyderabad Urban Realty - your trusted partner for premium real estate in Hyderabad.',
        url: 'https://www.hyderabadurbanrealty.com/about',
        mainEntity: this.seoService.generateOrganizationStructuredData()
      }
    });
  }

  openEnquiryModal(): void {
    this.showEnquiryModal = true;
  }

  closeEnquiryModal(): void {
    this.showEnquiryModal = false;
  }
}
