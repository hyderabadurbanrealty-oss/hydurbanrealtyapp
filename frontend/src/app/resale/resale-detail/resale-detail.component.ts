import { Component, OnInit, OnDestroy, ChangeDetectorRef } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { Subject } from 'rxjs';
import { takeUntil } from 'rxjs/operators';
import { environment } from '../../../environments/environment';
import { SeoService } from '../../services/seo.service';

const API = environment.apiUrl;

@Component({
  standalone: false,
  selector: 'app-resale-detail',
  templateUrl: './resale-detail.component.html',
  styleUrls: ['./resale-detail.component.css']
})
export class ResaleDetailComponent implements OnInit, OnDestroy {
  listing: any = null;
  loading     = true;
  error       = '';

  activeImage = 0;

  showVisit        = false;
  visitProjectName = '';
  visitProjectId   = '';

  private destroy$ = new Subject<void>();

  constructor(
    private route: ActivatedRoute,
    private router: Router,
    private http: HttpClient,
    private seo: SeoService,
    private cdr: ChangeDetectorRef
  ) {}

  ngOnInit(): void {
    this.route.paramMap.pipe(takeUntil(this.destroy$)).subscribe(params => {
      const slug = params.get('slug') ?? '';
      this.load(slug);
    });
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }

  load(slug: string): void {
    this.loading = true;
    this.error   = '';
    this.listing = null;

    this.http.get<any>(`${API}/resale/public/${slug}`).subscribe({
      next: data => {
        this.listing     = data;
        this.activeImage = 0;
        this.loading     = false;
        this.updateSeo(data, slug);
        this.cdr.markForCheck();
      },
      error: err => {
        this.loading = false;
        this.error = err.status === 404
          ? 'This listing is no longer available or has been removed.'
          : 'Failed to load listing. Please try again.';
        this.cdr.markForCheck();
      }
    });
  }

  private updateSeo(l: any, slug: string): void {
    const title = [l.project_name, l.configuration, l.location?.split(',')[0]?.trim()]
      .filter(Boolean).join(' · ');
    const price  = this.formatPrice(l.expected_price);
    const images = this.getImages(l);

    this.seo.updateTags({
      title:       `${title} — Resale | Hyderabad Urban Realty`,
      description: `Owner-listed resale property: ${title}. ${price}. ${l.super_built_up_area ? l.super_built_up_area + ' sq.ft · ' : ''}${l.age_of_property ?? ''}. View details and enquire.`,
      keywords:    `resale property hyderabad, ${l.location ?? ''}, ${l.configuration ?? ''}, ${l.project_name ?? ''}, owner listed`,
      url:         `https://www.hyderabadurbanrealty.com/resale/${slug}`,
      image:       images[0] ?? 'https://www.hyderabadurbanrealty.com/assets/blue-Logo.png',
      type:        'website',
      structuredData: {
        '@context': 'https://schema.org',
        '@type':    'RealEstateListing',
        name:       l.project_name ?? 'Resale Property',
        description: `${l.configuration ?? ''} in ${l.location ?? 'Hyderabad'}`,
        url:        `https://www.hyderabadurbanrealty.com/resale/${slug}`,
        image:      images,
        offers: {
          '@type':         'Offer',
          priceCurrency:   'INR',
          price:            l.expected_price ?? 0,
          availability:    'https://schema.org/InStock'
        },
        address: {
          '@type':          'PostalAddress',
          addressLocality:  l.location?.split(',')[0]?.trim() ?? 'Hyderabad',
          addressRegion:    'Telangana',
          addressCountry:   'IN'
        }
      }
    });
  }

  getImages(listing: any): string[] {
    try {
      const imgs = typeof listing?.images === 'string'
        ? JSON.parse(listing.images) : listing?.images;
      return Array.isArray(imgs) ? imgs : [];
    } catch { return []; }
  }

  getFeatures(listing: any): string[] {
    try {
      const f = typeof listing?.features === 'string'
        ? JSON.parse(listing.features) : listing?.features;
      return Array.isArray(f) ? f : [];
    } catch { return []; }
  }

  formatPrice(v: number): string {
    if (!v) return 'Price on request';
    if (v >= 10000000) return `₹${(v / 10000000).toFixed(2)} Cr`;
    if (v >= 100000)   return `₹${(v / 100000).toFixed(2)} L`;
    return `₹${v.toLocaleString('en-IN')}`;
  }

  openVisit(): void {
    const parts = [
      this.listing?.project_name,
      this.listing?.configuration,
      this.listing?.location?.split(',')[0]?.trim()
    ].filter(Boolean);
    this.visitProjectName = parts.join(' · ');
    this.visitProjectId   = this.listing?.id ?? '';
    this.showVisit        = true;
  }

  closeVisit(): void { this.showVisit = false; }

  prevImage(): void {
    const imgs = this.getImages(this.listing);
    this.activeImage = (this.activeImage - 1 + imgs.length) % imgs.length;
  }

  nextImage(): void {
    const imgs = this.getImages(this.listing);
    this.activeImage = (this.activeImage + 1) % imgs.length;
  }
}
