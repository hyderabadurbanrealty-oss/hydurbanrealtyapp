import { Component, OnInit, ChangeDetectorRef } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { environment } from '../../../environments/environment';

const API = environment.apiUrl;

@Component({
  standalone: false,
  selector: 'app-resale-browse',
  templateUrl: './resale-browse.component.html',
  styleUrls: ['./resale-browse.component.css']
})
export class ResaleBrowseComponent implements OnInit {
  listings: any[] = [];
  loading   = true;
  error     = '';
  total     = 0;
  page      = 1;
  pageSize  = 12;

  // Schedule visit modal
  showVisit        = false;
  visitProjectName = '';
  visitProjectId   = '';

  openVisit(listing: any): void {
    const parts = [listing.project_name, listing.configuration,
                   listing.location?.split(',')[0]?.trim()].filter(Boolean);
    this.visitProjectName = parts.join(' · ');
    this.visitProjectId   = listing.id ?? '';
    this.showVisit        = true;
  }

  closeVisit(): void { this.showVisit = false; }

  // Filters
  filterLocation      = '';
  filterConfiguration = '';
  filterMinPrice: number | null = null;
  filterMaxPrice: number | null = null;

  configurations = [
    '1 BHK', '2 BHK', '3 BHK', '4 BHK', '4+ BHK / Penthouse', 'Villa / Independent House'
  ];

  constructor(private http: HttpClient, private cdr: ChangeDetectorRef) {}

  ngOnInit(): void { this.load(); }

  load(): void {
    this.loading = true;
    this.error   = '';

    let params = new HttpParams()
      .set('page',     this.page)
      .set('pageSize', this.pageSize);

    if (this.filterLocation.trim())  params = params.set('location',     this.filterLocation.trim());
    if (this.filterConfiguration)    params = params.set('configuration', this.filterConfiguration);
    if (this.filterMinPrice != null) params = params.set('minPrice',      this.filterMinPrice);
    if (this.filterMaxPrice != null) params = params.set('maxPrice',      this.filterMaxPrice);

    this.http.get<any>(`${API}/resale/public`, { params }).subscribe({
      next: res => {
        this.listings = res.listings ?? [];
        this.total    = res.total    ?? 0;
        this.loading  = false;
        this.cdr.markForCheck();
      },
      error: () => {
        this.error   = 'Failed to load listings. Please try again.';
        this.loading = false;
        this.cdr.markForCheck();
      }
    });
  }

  applyFilters(): void {
    this.page = 1;
    this.load();
  }

  clearFilters(): void {
    this.filterLocation      = '';
    this.filterConfiguration = '';
    this.filterMinPrice      = null;
    this.filterMaxPrice      = null;
    this.page                = 1;
    this.load();
  }

  goToPage(p: number): void {
    this.page = p;
    this.load();
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  get totalPages(): number { return Math.ceil(this.total / this.pageSize); }
  get pages(): number[] {
    return Array.from({ length: this.totalPages }, (_, i) => i + 1);
  }

  getImages(listing: any): string[] {
    try {
      const imgs = typeof listing.images === 'string' ? JSON.parse(listing.images) : listing.images;
      return Array.isArray(imgs) ? imgs : [];
    } catch { return []; }
  }

  getFeatures(listing: any): string[] {
    try {
      const f = typeof listing.features === 'string' ? JSON.parse(listing.features) : listing.features;
      return Array.isArray(f) ? f : [];
    } catch { return []; }
  }

  formatPrice(v: number): string {
    if (!v) return 'Price on request';
    if (v >= 10000000) return `₹${(v / 10000000).toFixed(2)} Cr`;
    if (v >= 100000)   return `₹${(v / 100000).toFixed(2)} L`;
    return `₹${v.toLocaleString('en-IN')}`;
  }
}
