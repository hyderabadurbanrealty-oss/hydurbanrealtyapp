import { ChangeDetectorRef, Component, OnInit, OnDestroy } from '@angular/core';
import { Router } from '@angular/router';
import { Property } from '../map/map.component';
import { PropertyService } from '../services/property.service';
import { SearchService } from '../services/search.service';
import { LoadingService } from '../services/loading.service';
import { FavoriteService } from '../services/favorite.service';
import { CompareService, COMPARE_MAX } from '../services/compare.service';
import { AuthService } from '../services/auth.service';
import { MediaService } from '../services/media.service';
import { environment } from '../../environments/environment';
import { Subject, Subscription, of } from 'rxjs';
import { debounceTime, distinctUntilChanged, catchError } from 'rxjs/operators';

@Component({
  standalone: false,
  selector: 'app-home',
  templateUrl: './home.component.html',
  styleUrls: ['./home.component.css']
})
export class HomeComponent implements OnInit, OnDestroy {
  properties: Property[] = [];
  filtered: Property[] = [];
  q = '';
  selected: Property | null = null;
  drawerOpen = false;
  pulseMap = false;
  loading = true;
  error = '';
  sortBy = 'name';
  Math = Math;
  COMPARE_MAX = COMPARE_MAX;

  // Thumbnail map: projectId → first image URL
  thumbnails: Record<string, string> = {};

  // Compare panel
  compareList: Property[] = [];
  showComparePanel = false;
  private compareSub?: Subscription;

  // Toast
  toastMessage = '';
  toastType: 'success' | 'error' | 'info' = 'info';
  private toastTimer: any;

  districtData: Array<{name: string, count: number, percentage: number, totalArea: number}> = [];
  private searchSubject = new Subject<string>();

  constructor(
    private service: PropertyService,
    private router: Router,
    private searchService: SearchService,
    private loadingService: LoadingService,
    public favoriteService: FavoriteService,
    public compareService: CompareService,
    public auth: AuthService,
    private mediaService: MediaService,
    private cdr: ChangeDetectorRef
  ) {
    this.searchSubject.pipe(
      debounceTime(300),
      distinctUntilChanged()
    ).subscribe(query => this.performSearch(query));
  }

  ngOnInit(): void {
    this.compareSub = this.compareService.list$.subscribe(list => {
      this.compareList = list;
      this.showComparePanel = list.length > 0;
    });

    this.loading = true;
    this.service.getProperties().subscribe({
      next: (props) => {
        this.properties = props;
        this.filtered = props.slice();
        this.searchService.buildSearchIndex(props);
        this.loading = false;
        this.sortProperties();
        this.prepareDistrictData();
        this.loadThumbnails(props.slice(0, 12)); // preload first page
        this.cdr.detectChanges();
      },
      error: () => {
        this.error = 'Failed to load properties. Please try again later.';
        this.loading = false;
        this.cdr.detectChanges();
      }
    });
  }

  ngOnDestroy(): void {
    this.compareSub?.unsubscribe();
    clearTimeout(this.toastTimer);
  }

  // ── Thumbnails ───────────────────────────────────────────────────────────

  private loadThumbnails(props: Property[]) {
    props.forEach(p => {
      const id = this.getPropId(p);
      if (!id) return;
      this.mediaService.getMedia(id, 'image').pipe(
        catchError(() => of([]))
      ).subscribe((mediaList: any) => {
        if (Array.isArray(mediaList) && mediaList.length > 0) {
          this.thumbnails[id] = mediaList[0].fileUrl || mediaList[0].file_url || '';
        } else {
          const legacyImg = (p as any)?.media?.images?.[0];
          if (legacyImg) this.thumbnails[id] = `${environment.apiUrl}/projects/${id}/media/${legacyImg}`;
        }
        this.cdr.detectChanges();
      });
    });
  }

  getThumbnail(p: Property): string {
    return this.thumbnails[this.getPropId(p)] || '';
  }

  getPropId(p: Property): string {
    return (p as any).id ?? (p as any).projectId ?? '';
  }

  // ── Favorite ─────────────────────────────────────────────────────────────

  toggleFavorite(p: Property, event: Event) {
    event.stopPropagation();
    const added = this.favoriteService.toggleFavorite(p);
    this.showToast(
      added ? `Added to favorites` : `Removed from favorites`,
      added ? 'success' : 'info'
    );
  }

  isFavorite(p: Property): boolean {
    return this.favoriteService.isFavorite(this.getPropId(p));
  }

  // ── Compare ──────────────────────────────────────────────────────────────

  toggleCompare(p: Property, event: Event) {
    event.stopPropagation();
    const id = this.getPropId(p);
    const name = (p as any)['Project Name'] || 'Property';
    if (this.compareService.isInList(id)) {
      this.compareService.remove(id);
      this.showToast(`${name} removed from compare`, 'info');
    } else {
      if (!this.compareService.canAdd()) {
        this.showToast(`Max ${COMPARE_MAX} properties for compare`, 'error');
        return;
      }
      this.compareService.add(p);
      this.showToast(`${name} added to compare`, 'success');
    }
  }

  isInCompare(p: Property): boolean {
    return this.compareService.isInList(this.getPropId(p));
  }

  removeFromCompare(p: Property, event: Event) {
    event.stopPropagation();
    this.compareService.remove(this.getPropId(p));
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

  goToComparePage() { this.router.navigate(['/comparison']); }

  // ── Enquiry / WhatsApp ───────────────────────────────────────────────────

  openEnquiry(p: Property, event: Event) {
    event.stopPropagation();
    if (!this.auth.isLoggedIn()) {
      this.router.navigate(['/login'], { queryParams: { returnUrl: '/' } });
      return;
    }
    const user = this.auth.getCurrentUser();
    const propName = (p as any)['Project Name'] || '';
    const locality = (p as any)['Locality'] || (p as any)['locality'] || '';
    const district = (p as any)['District'] || (p as any)['district'] || '';
    const location = [locality, district].filter(Boolean).join(', ') || 'Hyderabad';
    const id = this.getPropId(p);

    const msg = [
      `Hi, I'm interested in *${propName}*`,
      `📍 ${location}`,
      id ? `🔗 ${window.location.origin}/property/${id}` : '',
      ``,
      `👤 ${user?.fullName || ''}`,
      `📧 ${user?.email || ''}`,
      user?.mobile ? `📱 ${user.mobile}` : '',
      ``,
      `Please share more details. Thank you!`
    ].filter(l => l !== undefined).join('\n');

    window.open(`https://wa.me/919100000000?text=${encodeURIComponent(msg)}`, '_blank');
  }

  // ── Toast ────────────────────────────────────────────────────────────────

  showToast(message: string, type: 'success' | 'error' | 'info' = 'info') {
    clearTimeout(this.toastTimer);
    this.toastMessage = message;
    this.toastType = type;
    this.toastTimer = setTimeout(() => { this.toastMessage = ''; }, 3000);
  }

  // ── Existing methods ─────────────────────────────────────────────────────

  filter() { this.searchSubject.next(this.q); }

  private performSearch(query: string) {
    const q = (query || '').trim();
    this.filtered = q ? this.searchService.search(q) : this.properties.slice();
    this.sortProperties();
  }

  sortProperties() {
    this.filtered.sort((a, b) => {
      if (this.sortBy === 'name') return (a['Project Name'] || '').localeCompare(b['Project Name'] || '');
      if (this.sortBy === 'area') return parseFloat(b['Total Area(In sqmts)'] || '0') - parseFloat(a['Total Area(In sqmts)'] || '0');
      if (this.sortBy === 'date') return this.parseDate(b['Approved Date'] || '').getTime() - this.parseDate(a['Approved Date'] || '').getTime();
      return 0;
    });
  }

  parseDate(dateStr: string): Date {
    if (!dateStr) return new Date(0);
    const parts = dateStr.split('/');
    if (parts.length === 3) return new Date(parseInt(parts[2]), parseInt(parts[1]) - 1, parseInt(parts[0]));
    return new Date(0);
  }

  formatArea(area: string | undefined): string {
    if (!area) return 'N/A';
    const num = parseFloat(area);
    if (isNaN(num)) return area;
    return num.toLocaleString('en-IN', { maximumFractionDigits: 2 }) + ' sq.m';
  }

  formatAreaInKm(area: number): string { return (area / 1000000).toFixed(2); }
  formatDate(dateStr: string | undefined): string { return dateStr || 'N/A'; }

  getStatusBadgeClass(status: string | undefined): string {
    if (!status) return 'status-unknown';
    if (status.toLowerCase().includes('completed')) return 'status-completed';
    if (status.toLowerCase().includes('ongoing')) return 'status-ongoing';
    if (status.toLowerCase().includes('new')) return 'status-new';
    return 'status-unknown';
  }

  getStatusLabel(status: string): string {
    const s = status.toLowerCase();
    if (s.includes('completed')) return 'Completed';
    if (s.includes('ongoing')) return 'Ongoing';
    if (s.includes('new')) return 'New Launch';
    return status;
  }

  focusOn(p: Property) { this.pulseMap = true; setTimeout(() => (this.pulseMap = false), 900); this.selected = p; this.drawerOpen = true; }
  openDetails(p: Property) {
    if (p?.id) { this.loadingService.show(); requestAnimationFrame(() => setTimeout(() => this.router.navigate(['/property', p.id]), 0)); }
  }
  onPick(p: Property) { this.selected = p; this.drawerOpen = true; }
  closeDrawer() { this.drawerOpen = false; this.selected = null; }
  viewAllProperties() { this.router.navigate(['/properties']); }
  navigateToDetails(propertyId: string) { this.loadingService.show(); requestAnimationFrame(() => setTimeout(() => this.router.navigate(['/property', propertyId]), 0)); }
  exploreLocality(locality: string) { this.router.navigate(['/properties'], { queryParams: { q: locality } }); }
  onSearch(query: string) { this.q = query; this.filter(); }
  clearSearch() { this.q = ''; this.filter(); }

  prepareDistrictData() {
    const districtMap = new Map<string, {display: string; count: number; totalArea: number}>();
    this.properties.forEach(p => {
      const raw = (p['Locality'] || p['Village/City/Town'] || p['Mandal'] || p['District'] || '').toString().trim();
      if (!raw) return; // skip properties with no location data
      const key = raw.toLowerCase();
      const area = parseFloat(p['Total Area(In sqmts)'] || '0');
      if (districtMap.has(key)) { const e = districtMap.get(key)!; e.count++; e.totalArea += area; }
      else districtMap.set(key, { display: raw, count: 1, totalArea: area });
    });
    const total = this.properties.length;
    this.districtData = Array.from(districtMap.values())
      .map(d => ({ name: d.display, count: d.count, totalArea: d.totalArea, percentage: Math.round((d.count / total) * 100) }))
      .sort((a, b) => b.count - a.count).slice(0, 10);
  }
}
