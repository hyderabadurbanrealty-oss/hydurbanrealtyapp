import { Component, OnInit } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { environment } from '../../../environments/environment';

const API = environment.apiUrl;

@Component({
  standalone: false,
  selector: 'app-resale-listings',
  templateUrl: './resale-listings.component.html',
  styleUrls: ['./resale-listings.component.css']
})
export class ResaleListingsComponent implements OnInit {
  listings: any[] = [];
  loading  = true;
  error    = '';
  deleting: string | null = null;

  constructor(private http: HttpClient) {}

  ngOnInit(): void { this.load(); }

  load(): void {
    this.loading = true;
    this.error   = '';
    this.http.get<any>(`${API}/resale/my`).subscribe({
      next: res => { this.listings = res.listings || []; this.loading = false; },
      error: () => { this.error = 'Failed to load listings. Please try again.'; this.loading = false; }
    });
  }

  delete(id: string): void {
    if (!confirm('Remove this listing?')) return;
    this.deleting = id;
    this.http.delete(`${API}/resale/${id}`).subscribe({
      next: () => {
        this.listings = this.listings.filter(l => l.id !== id);
        this.deleting = null;
      },
      error: () => { this.deleting = null; alert('Failed to delete listing.'); }
    });
  }

  getImages(listing: any): string[] {
    try {
      const imgs = typeof listing.images === 'string'
        ? JSON.parse(listing.images) : listing.images;
      return Array.isArray(imgs) ? imgs : [];
    } catch { return []; }
  }

  getFeatures(listing: any): string[] {
    try {
      const f = typeof listing.features === 'string'
        ? JSON.parse(listing.features) : listing.features;
      return Array.isArray(f) ? f : [];
    } catch { return []; }
  }

  statusClass(status: string): string {
    const map: Record<string, string> = {
      pending:  'badge--pending',
      active:   'badge--active',
      sold:     'badge--sold',
      rejected: 'badge--rejected'
    };
    return map[status] || 'badge--pending';
  }

  formatPrice(v: number): string {
    if (!v) return 'Price not specified';
    if (v >= 10000000) return `₹${(v / 10000000).toFixed(2)} Cr`;
    if (v >= 100000)   return `₹${(v / 100000).toFixed(2)} L`;
    return `₹${v.toLocaleString('en-IN')}`;
  }

  formatDate(d: string): string {
    return d ? new Date(d).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }) : '';
  }
}
