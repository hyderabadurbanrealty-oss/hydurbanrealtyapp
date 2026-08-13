import { Component, OnInit, OnDestroy } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { take, catchError } from 'rxjs/operators';
import { forkJoin, of, Subscription } from 'rxjs';
import { Property } from '../map/map.component';
import { PropertyService } from '../services/property.service';
import { LoadingService } from '../services/loading.service';
import { FavoriteService } from '../services/favorite.service';
import { CompareService, COMPARE_MAX } from '../services/compare.service';
import { AuthService } from '../services/auth.service';
import { MediaService } from '../services/media.service';

@Component({
  selector: 'app-properties',
  templateUrl: './properties.component.html',
  styleUrls: ['./properties.component.css']
})
export class PropertiesComponent implements OnInit, OnDestroy {
  properties: Property[] = [];
  filtered: Property[] = [];
  searchQuery = '';
  sortBy = 'name';
  filterType = 'all';
  loading = true;
  error = '';
  Math = Math;
  COMPARE_MAX = COMPARE_MAX;

  projectTypes: string[] = ['All'];
  projectStatuses: string[] = ['All'];
  selectedType = 'All';
  selectedStatus = 'All';

  // Thumbnail map: projectId → first image URL
  thumbnails: Record<string, string> = {};

  // Compare panel
  compareList: Property[] = [];
  showComparePanel = false;
  private compareSub?: Subscription;

  // Toast notification
  toastMessage = '';
  toastType: 'success' | 'error' | 'info' = 'info';
  private toastTimer: any;

  constructor(
    private propertyService: PropertyService,
    private router: Router,
    private loadingService: LoadingService,
    private route: ActivatedRoute,
    public favoriteService: FavoriteService,
    public compareService: CompareService,
    public auth: AuthService,
    private mediaService: MediaService
  ) {}

  ngOnInit() {
    // Subscribe to compare list changes
    this.compareSub = this.compareService.list$.subscribe(list => {
      this.compareList = list;
      this.showComparePanel = list.length > 0;
    });

    // Pre-populate search from query param, then load
    this.route.queryParams.pipe(take(1)).subscribe(params => {
      if (params['q']) {
        this.searchQuery = params['q'];
      }
      this.loadProperties();
    });
  }

  ngOnDestroy() {
    this.compareSub?.unsubscribe();
  }

  loadProperties() {
    this.loading = true;
    this.propertyService.getProperties().subscribe({
      next: (props) => {
        this.properties = props;
        this.filtered = props;
        this.loading = false;
        this.buildFilterOptions();
        this.applyFilters();
        // Load thumbnails lazily for visible properties
        this.loadThumbnails(props);
      },
      error: () => {
        this.error = 'Failed to load properties';
        this.loading = false;
      }
    });
  }

  /** Load first image for each property — batch in groups of 10 to avoid hammering the API */
  private loadThumbnails(props: Property[]) {
    const BATCH = 10;
    const chunks: Property[][] = [];
    for (let i = 0; i < props.length; i += BATCH) {
      chunks.push(props.slice(i, i + BATCH));
    }

    const processChunk = (idx: number) => {
      if (idx >= chunks.length) return;
      const chunk = chunks[idx];
      const requests = chunk.map(p => {
        const id = this.getPropId(p);
        if (!id) return of(null);
        return this.mediaService.getMedia(id, 'image').pipe(
          catchError(() => of([]))
        );
      });

      forkJoin(requests).subscribe(results => {
        results.forEach((mediaList: any, i) => {
          const id = this.getPropId(chunk[i]);
          if (!id) return;
          if (Array.isArray(mediaList) && mediaList.length > 0) {
            const first = mediaList[0];
            this.thumbnails[id] = first.fileUrl || first.file_url || '';
          } else {
            // Try legacy image from property data
            const prop = chunk[i] as any;
            const legacyImg = prop?.media?.images?.[0];
            if (legacyImg) {
              this.thumbnails[id] = `/api/projects/${id}/media/${legacyImg}`;
            }
          }
        });
        // Process next batch after a short delay
        setTimeout(() => processChunk(idx + 1), 200);
      });
    };

    processChunk(0);
  }

  getThumbnail(property: Property): string {
    const id = this.getPropId(property);
    return id ? (this.thumbnails[id] || '') : '';
  }

  getPropId(property: Property): string {
    return (property as any).id ?? (property as any).projectId ?? '';
  }

  buildFilterOptions() {
    const uniqueTypes = new Set<string>();
    const uniqueStatuses = new Set<string>();
    this.properties.forEach(prop => {
      const type = (prop as any)['Project Type'] || (prop as any)['projectType'];
      const status = (prop as any)['Project Status'] || (prop as any)['projectStatus'];
      if (type && typeof type === 'string' && type.trim()) uniqueTypes.add(type.trim());
      if (status && typeof status === 'string' && status.trim()) uniqueStatuses.add(status.trim());
    });
    this.projectTypes = ['All', ...Array.from(uniqueTypes).sort()];
    this.projectStatuses = ['All', ...Array.from(uniqueStatuses).sort()];
  }

  applyFilters() {
    let result = [...this.properties];

    if (this.searchQuery.trim()) {
      const query = this.searchQuery.toLowerCase();
      result = result.filter(p =>
        ((p as any)['Project Name'] || '').toLowerCase().includes(query) ||
        ((p as any)['Locality'] || '').toLowerCase().includes(query) ||
        ((p as any)['District'] || '').toLowerCase().includes(query) ||
        ((p as any)['Village/City/Town'] || '').toLowerCase().includes(query) ||
        ((p as any)['projectName'] || '').toLowerCase().includes(query) ||
        ((p as any)['locality'] || '').toLowerCase().includes(query) ||
        ((p as any)['district'] || '').toLowerCase().includes(query)
      );
    }

    if (this.selectedType !== 'All') {
      result = result.filter(p => {
        const type = (p as any)['Project Type'] || (p as any)['projectType'];
        return type && type.trim() === this.selectedType;
      });
    }

    if (this.selectedStatus !== 'All') {
      result = result.filter(p => {
        const status = (p as any)['Project Status'] || (p as any)['projectStatus'];
        return status && status.trim() === this.selectedStatus;
      });
    }

    this.filtered = result;
    this.sortProperties();
  }

  sortProperties() {
    if (this.sortBy === 'name') {
      this.filtered.sort((a, b) =>
        ((a as any)['Project Name'] || '').localeCompare((b as any)['Project Name'] || '')
      );
    } else if (this.sortBy === 'area') {
      this.filtered.sort((a, b) => {
        const areaA = parseFloat((a as any)['Total Area(In sqmts)'] || '0');
        const areaB = parseFloat((b as any)['Total Area(In sqmts)'] || '0');
        return areaB - areaA;
      });
    } else if (this.sortBy === 'rating') {
      this.filtered.sort((a, b) =>
        ((b as any).averageRating || 0) - ((a as any).averageRating || 0)
      );
    }
  }

  viewDetails(property: Property) {
    const id = this.getPropId(property);
    if (id) {
      this.loadingService.show();
      requestAnimationFrame(() => setTimeout(() => this.router.navigate(['/property', id]), 0));
    }
  }

  // ── Favorite ────────────────────────────────────────────────────────────

  toggleFavorite(property: Property, event: Event) {
    event.stopPropagation();
    const added = this.favoriteService.toggleFavorite(property);
    const name = (property as any)['Project Name'] || 'Property';
    this.showToast(
      added ? `${name} added to favorites` : `${name} removed from favorites`,
      added ? 'success' : 'info'
    );
  }

  isFavorite(property: Property): boolean {
    return this.favoriteService.isFavorite(this.getPropId(property));
  }

  // ── Compare ─────────────────────────────────────────────────────────────

  toggleCompare(property: Property, event: Event) {
    event.stopPropagation();
    const id = this.getPropId(property);
    const name = (property as any)['Project Name'] || 'Property';

    if (this.compareService.isInList(id)) {
      this.compareService.remove(id);
      this.showToast(`${name} removed from compare`, 'info');
    } else {
      if (!this.compareService.canAdd()) {
        this.showToast(`You can compare up to ${COMPARE_MAX} properties only`, 'error');
        return;
      }
      this.compareService.add(property);
      this.showToast(`${name} added to compare`, 'success');
    }
  }

  isInCompare(property: Property): boolean {
    return this.compareService.isInList(this.getPropId(property));
  }

  removeFromCompare(property: Property, event: Event) {
    event.stopPropagation();
    this.compareService.remove(this.getPropId(property));
  }

  goToComparePage() {
    this.router.navigate(['/comparison']);
  }

  getCompareItemName(p: Property): string {
    return (p as any)['Project Name'] || (p as any)['projectName'] || 'Property';
  }

  getCompareItemLocation(p: Property): string {
    const loc = (p as any)['Locality'] || (p as any)['locality'] || '';
    const dist = (p as any)['District'] || (p as any)['district'] || '';
    return [loc, dist].filter(Boolean).join(', ') || 'N/A';
  }

  getCompareSlots(): number[] {
    return Array(Math.max(0, COMPARE_MAX - this.compareList.length)).fill(0);
  }

  // ── Enquiry / WhatsApp ───────────────────────────────────────────────────

  openEnquiry(property: Property, event: Event) {
    event.stopPropagation();

    if (!this.auth.isLoggedIn()) {
      this.router.navigate(['/login'], { queryParams: { returnUrl: '/properties' } });
      return;
    }

    const user = this.auth.getCurrentUser();
    const propName = (property as any)['Project Name'] || (property as any)['projectName'] || 'Property';
    const locality = (property as any)['Locality'] || (property as any)['locality'] || '';
    const district = (property as any)['District'] || (property as any)['district'] || '';
    const location = [locality, district].filter(Boolean).join(', ') || 'Hyderabad';
    const propType = (property as any)['Project Type'] || (property as any)['projectType'] || '';
    const status = (property as any)['Project Status'] || (property as any)['projectStatus'] || '';
    const id = this.getPropId(property);

    const message = [
      `Hi, I'm interested in the property *${propName}*`,
      `📍 Location: ${location}`,
      propType ? `🏗️ Type: ${propType}` : '',
      status ? `📋 Status: ${status}` : '',
      id ? `🔗 Ref: ${window.location.origin}/property/${id}` : '',
      ``,
      `My details:`,
      `👤 Name: ${user?.fullName || ''}`,
      `📧 Email: ${user?.email || ''}`,
      user?.mobile ? `📱 Mobile: ${user.mobile}` : '',
      ``,
      `Please share more information about this project. Thank you!`
    ].filter(l => l !== null && l !== undefined && l !== '').join('\n');

    const phone = '919100000000'; // Replace with actual business WhatsApp number
    const encodedMessage = encodeURIComponent(message);
    window.open(`https://wa.me/${phone}?text=${encodedMessage}`, '_blank');
  }

  // ── Helpers ──────────────────────────────────────────────────────────────

  formatArea(area: string | undefined): string {
    if (!area) return 'N/A';
    const num = parseFloat(area);
    if (isNaN(num)) return area;
    return num.toLocaleString('en-IN', { maximumFractionDigits: 0 }) + ' sqm';
  }

  getStatusBadgeClass(status: string): string {
    if (!status) return '';
    const s = status.toLowerCase();
    if (s.includes('completed')) return 'status-completed';
    if (s.includes('ongoing')) return 'status-ongoing';
    if (s.includes('new')) return 'status-new';
    return '';
  }

  getStatusLabel(status: string): string {
    if (!status) return '';
    const s = status.toLowerCase();
    if (s.includes('completed')) return 'Completed';
    if (s.includes('ongoing')) return 'Ongoing';
    if (s.includes('new')) return 'New Launch';
    return status;
  }

  showToast(message: string, type: 'success' | 'error' | 'info' = 'info') {
    clearTimeout(this.toastTimer);
    this.toastMessage = message;
    this.toastType = type;
    this.toastTimer = setTimeout(() => { this.toastMessage = ''; }, 3000);
  }
}
