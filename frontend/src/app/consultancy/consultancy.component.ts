import { Component, OnInit, ChangeDetectorRef } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { SeoService } from '../services/seo.service';

@Component({
  standalone: false,
  selector: 'app-consultancy',
  templateUrl: './consultancy.component.html',
  styleUrls: ['./consultancy.component.css']
})
export class ConsultancyComponent implements OnInit {
  // Enquiry Form
  showEnquiryModal = false;
  enquiryForm = {
    name: '',
    email: '',
    phone: '',
    propertyType: 'residential',
    consultationType: 'investment',
    budget: '',
    location: '',
    message: ''
  };
  
  enquirySubmitting = false;
  enquirySuccess = false;
  enquiryError = '';

  // Market Insights Data
  marketInsights = {
    avgPSF: 9029,
    yoyGrowth: 6.3,
    rentalYield: '3.2-3.6',
    inventoryMonths: 31,
    q4Sales: 9887,
    topLocations: [
      { name: 'South West', psf: 10296, growth: 12.8 },
      { name: 'Greater Hyderabad', psf: 8486, growth: 14.2 },
      { name: 'North West', psf: 9032, growth: 3.0 },
      { name: 'North East', psf: 7087, growth: 8.1 }
    ]
  };

  // Expertise Areas
  expertiseAreas = [
    {
      icon: '🏢',
      title: 'Investment Advisory',
      description: 'Strategic property investment guidance with data-driven market analysis and ROI projections'
    },
    {
      icon: '🏡',
      title: 'Home Purchase Consulting',
      description: 'End-to-end assistance in finding your dream home with location analysis and price negotiation'
    },
    {
      icon: '📊',
      title: 'Market Research',
      description: 'Comprehensive market intelligence on pricing trends, emerging localities, and growth corridors'
    },
    {
      icon: '⚖️',
      title: 'RERA Compliance',
      description: '100% RERA verified properties with complete legal due diligence and documentation support'
    },
    {
      icon: '💼',
      title: 'Portfolio Management',
      description: 'Strategic management of real estate portfolios to maximize returns and minimize risks'
    },
    {
      icon: '🎯',
      title: 'Exit Strategy Planning',
      description: 'Optimal timing and pricing strategies for property sales to maximize capital gains'
    }
  ];

  // Growth Corridors
  growthCorridors = [
    {
      name: 'Western Corridor',
      areas: 'Kokapet, Neopolis, Financial District, Narsingi, Puppalaguda',
      strength: 'Proximity to IT/Business districts, Premium developments',
      rating: 5
    },
    {
      name: 'Emerging Markets',
      areas: 'Tellapur, Kollur, Osman Nagar',
      strength: 'ORR connectivity, Large gated communities',
      rating: 4
    },
    {
      name: 'Southern Growth Belt',
      areas: 'Budvel, Shamshabad',
      strength: 'Airport proximity, Integrated townships',
      rating: 4
    }
  ];

  // Stats
  stats = [
    { value: '500+', label: 'Properties Analyzed', icon: '🏘️' },
    { value: '100%', label: 'RERA Verified', icon: '✓' },
    { value: '12.8%', label: 'Avg. Annual Growth', icon: '📈' },
    { value: '24/7', label: 'Expert Support', icon: '💬' }
  ];

  // Why Choose Us
  whyChooseUs = [
    {
      icon: '📊',
      title: 'Data-Driven Insights',
      description: 'Real-time market analytics powered by comprehensive research and ground intelligence'
    },
    {
      icon: '🎯',
      title: 'Hyderabad Market Specialists',
      description: 'Deep expertise in Hyderabad\'s residential corridors, pricing dynamics, and growth patterns'
    },
    {
      icon: '🤝',
      title: 'End-to-End Support',
      description: 'From property search to final registration - complete handholding throughout the journey'
    },
    {
      icon: '🔍',
      title: 'Transparent Process',
      description: 'No hidden charges, complete disclosure, and unbiased recommendations focused on your goals'
    }
  ];

  constructor(
    private http: HttpClient,
    private cdr: ChangeDetectorRef,
    private seoService: SeoService
  ) {}

  ngOnInit(): void {
    // Set SEO meta tags with comprehensive metadata
    this.seoService.updateTags({
      title: 'Expert Property Consultancy Services in Hyderabad | Real Estate Advisory | Hyderabad Urban Realty',
      description: 'Professional property consultancy services in Hyderabad with Q4 2025 market insights. Investment advisory, home buying guidance, RERA compliance, and portfolio management. Get expert real estate consultation backed by comprehensive market data. Free consultation available.',
      keywords: 'property consultancy hyderabad, real estate advisory hyderabad, investment consulting, home buying consultant, property advisor, market research hyderabad, RERA verified properties, property investment advisor, real estate expert hyderabad, hyderabad property consultant, property portfolio management, real estate due diligence, property market analysis, hyderabad housing market, investment property guidance',
      url: 'https://www.hyderabadurbanrealty.com/consultancy',
      image: 'https://www.hyderabadurbanrealty.com/assets/blue-Logo.png',
      type: 'website',
      author: 'Hyderabad Urban Realty',
      structuredData: {
        '@context': 'https://schema.org',
        '@type': 'ProfessionalService',
        name: 'Hyderabad Urban Realty - Property Consultancy Services',
        description: 'Expert property consultancy and real estate advisory services in Hyderabad with comprehensive market insights',
        url: 'https://www.hyderabadurbanrealty.com/consultancy',
        areaServed: {
          '@type': 'City',
          name: 'Hyderabad',
          '@id': 'https://en.wikipedia.org/wiki/Hyderabad'
        },
        priceRange: 'Free Consultation',
        telephone: '+91-8977367700',
        email: 'hyderabadurbanrealty@gmail.com',
        address: {
          '@type': 'PostalAddress',
          addressLocality: 'Hyderabad',
          addressRegion: 'Telangana',
          addressCountry: 'IN'
        },
        serviceType: [
          'Property Investment Advisory',
          'Home Purchase Consulting',
          'Market Research & Analysis',
          'RERA Compliance Verification',
          'Portfolio Management',
          'Exit Strategy Planning'
        ],
        hasOfferCatalog: {
          '@type': 'OfferCatalog',
          name: 'Property Consultancy Services',
          itemListElement: [
            {
              '@type': 'Offer',
              itemOffered: {
                '@type': 'Service',
                name: 'Investment Advisory',
                description: 'Strategic property investment guidance with data-driven market analysis and ROI projections'
              }
            },
            {
              '@type': 'Offer',
              itemOffered: {
                '@type': 'Service',
                name: 'Home Purchase Consulting',
                description: 'End-to-end assistance in finding your dream home with location analysis and price negotiation'
              }
            },
            {
              '@type': 'Offer',
              itemOffered: {
                '@type': 'Service',
                name: 'Market Research',
                description: 'Comprehensive market intelligence on pricing trends, emerging localities, and growth corridors'
              }
            }
          ]
        },
        aggregateRating: {
          '@type': 'AggregateRating',
          ratingValue: '4.8',
          reviewCount: '127'
        },
        contactPoint: {
          '@type': 'ContactPoint',
          telephone: '+91-8977367700',
          email: 'hyderabadurbanrealty@gmail.com',
          contactType: 'Customer Service',
          availableLanguage: ['English', 'Hindi', 'Telugu']
        }
      }
    });
  }

  openEnquiryModal(): void {
    // Smooth scroll to inline form instead of opening modal
    this.scrollToForm();
  }

  closeEnquiryModal(): void {
    this.showEnquiryModal = false;
    this.resetForm();
  }

  submitEnquiry(): void {
    // Validation
    if (!this.enquiryForm.name || !this.enquiryForm.phone) {
      this.enquiryError = 'Please fill in all required fields';
      return;
    }

    this.enquirySubmitting = true;
    this.enquiryError = '';

    const payload = {
      name: this.enquiryForm.name.trim(),
      email: this.enquiryForm.email.trim(),
      mobile: this.enquiryForm.phone.trim(), // Backend expects 'mobile' not 'phone'
      areaOfInterest: `${this.enquiryForm.consultationType} - ${this.enquiryForm.propertyType}${this.enquiryForm.budget ? ' - Budget: ' + this.enquiryForm.budget : ''}${this.enquiryForm.location ? ' - Location: ' + this.enquiryForm.location : ''}${this.enquiryForm.message ? ' - ' + this.enquiryForm.message : ''}`,
      source: 'consultancy_page'
    };

    this.http.post('/api/submit_lead', payload).subscribe({
      next: () => {
        this.enquirySubmitting = false;
        this.enquirySuccess = true;
        this.cdr.detectChanges();
        setTimeout(() => {
          this.enquirySuccess = false;
          this.resetForm();
        }, 3000);
      },
      error: (err) => {
        console.error('Enquiry submission error:', err);
        this.enquirySubmitting = false;
        this.enquiryError = err?.error?.message || 'Failed to submit enquiry. Please try again or call us at +91 8977 367700';
        this.cdr.detectChanges();
      }
    });
  }

  resetForm(): void {
    this.enquiryForm = {
      name: '',
      email: '',
      phone: '',
      propertyType: 'residential',
      consultationType: 'investment',
      budget: '',
      location: '',
      message: ''
    };
  }

  scrollToMarketReport(): void {
    const el = document.getElementById('market-report');
    if (el) {
      const top = el.getBoundingClientRect().top + window.pageYOffset - 80;
      window.scrollTo({ top, behavior: 'smooth' });
    }
  }

  scrollToForm(): void {
    const formElement = document.querySelector('.cta-form-section');
    if (formElement) {
      // Smooth scroll with offset for better visibility
      const elementPosition = formElement.getBoundingClientRect().top + window.pageYOffset;
      const offsetPosition = elementPosition - 80; // Offset for header
      
      window.scrollTo({
        top: offsetPosition,
        behavior: 'smooth'
      });
      
      // Add a brief highlight effect to draw attention
      setTimeout(() => {
        formElement.classList.add('form-highlight');
        setTimeout(() => {
          formElement.classList.remove('form-highlight');
        }, 2000);
      }, 500);
    }
  }
}
