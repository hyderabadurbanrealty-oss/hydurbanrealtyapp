import { Component, OnInit, OnDestroy } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { Subscription, forkJoin } from 'rxjs';
import { catchError, of } from 'rxjs';
import { Property } from '../map/map.component';
import { FavoriteService } from '../services/favorite.service';
import { PropertyService } from '../services/property.service';
import { UserDataService } from '../services/user-data.service';
import { AuthService } from '../services/auth.service';
import { MediaService, PropertyMedia } from '../services/media.service';
import { LoadingService } from '../services/loading.service';
import { ChartData, ChartOptions } from 'chart.js';
import { environment } from '../../environments/environment';

@Component({
  selector: 'app-property-detail',
  templateUrl: './property-detail.component.html',
  styleUrls: ['./property-detail.component.css']
})
export class PropertyDetailComponent implements OnInit, OnDestroy {
  property?: any; // Changed to any to support extended data
  reviews: any[] = [];
  averageRating: number = 0;
  showReviewForm = false;
  activeTab: 'overview' | 'rera' | 'pricing' | 'amenities' | 'details' | 'reviews' | 'documents' | 'floorplans' = 'overview';
  loading = true;
  error = '';
  Math = Math; // Expose Math to template
  Object = Object; // Expose Object to template

  isFavorite = false;
  isSaved = false;
  savePropertyNote = '';
  savingProperty = false;
  savePropertySuccess = '';

  // ── Media from DB ─────────────────────────────────────────────────────────
  propertyImages: PropertyMedia[] = [];
  propertyFloorplans: PropertyMedia[] = [];
  propertyDocuments: PropertyMedia[] = [];
  propertyVideos: PropertyMedia[] = [];
  mediaLoaded = false;
  activeImageIndex = 0;
  showImageLightbox = false;
  lightboxImages: PropertyMedia[] = [];
  lightboxIndex = 0;

  // ── Latest Properties ─────────────────────────────────────────────────────
  latestProperties: Property[] = [];
  loadingLatestProperties = false;
  latestPropertyThumbnails: Record<string, string> = {};

  private favSub?: Subscription;

  // Price history / trend chart
  priceHistory: any[] = [];
  priceChartData: ChartData<'line'> = { labels: [], datasets: [] };
  priceChartOptions: ChartOptions<'line'> = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    plugins: {
      legend: {
        display: true,
        position: 'top',
        labels: {
          usePointStyle: true,
          padding: 20,
          font: { size: 13 } as any,
          filter: (item) => !item.text?.includes('(Projected)')
        }
      },
      tooltip: {
        backgroundColor: 'rgba(15,23,42,0.92)',
        padding: 14,
        titleFont: { size: 13, weight: 'bold' } as any,
        bodyFont: { size: 13 } as any,
        cornerRadius: 10,
        boxPadding: 6,
        callbacks: {
          title: (items) => items[0]?.label ?? '',
          label: (ctx) => {
            if (ctx.parsed.y == null) return '';
            const suffix = ctx.dataset.label?.includes('(Projected)') ? ' (projected)' : '';
            return `  ${ctx.dataset.label?.replace(' (Projected)','')}${suffix}: ₹${ctx.parsed.y.toLocaleString('en-IN')}/sqft`;
          }
        }
      }
    },
    scales: {
      x: {
        grid: { color: 'rgba(148,163,184,0.12)' },
        ticks: { font: { size: 12 } as any, color: '#64748b' }
      },
      y: {
        grid: { color: 'rgba(148,163,184,0.12)' },
        ticks: {
          font: { size: 12 } as any,
          color: '#64748b',
          callback: (v) => '₹' + Number(v).toLocaleString('en-IN')
        }
      }
    },
    animation: { duration: 900, easing: 'easeOutQuart' } as any
  };
  hasPriceHistory = false;
  allUnitTypes: string[] = [];
  selectedUnitType: string = 'All';
  priceStats: { type: string; current: number; change: number; changePct: number; color: string }[] = [];
  private allPriceDatasets: any[] = [];
  private priceChartAllLabels: string[] = [];

  // ── SRO registered transaction trend ─────────────────────────────────────
  hasSroTrend = false;
  sroTrendQuarters: any[] = [];
  sroTrendMatchedApts: string[] = [];
  sroTrendTotalTx = 0;
  sroTrendChart: ChartData<'line'> = { labels: [], datasets: [] };

  // ── SRO registration / booking status ────────────────────────────────────
  sroUnits: {
    found: boolean;
    total_registered: number;
    unique_flats_registered: number;
    total_value_cr: number;
    by_quarter: { quarter: string; count: number; unique_flats: number; total_value_cr: number }[];
    recent_quarter: string;
    recent_count: number;
    matched_apartments: string[];
  } | null = null;
  sroTrendOptions: ChartOptions<'line'> = {
    responsive: true, maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: 'rgba(15,23,42,0.92)',
        padding: 12,
        cornerRadius: 10,
        callbacks: {
          title: (items) => items[0]?.label ?? '',
          label: (ctx) => `  Avg ₹${Number(ctx.parsed.y).toLocaleString('en-IN')}/sqft  (${(ctx.raw as any)?._count ?? ''} deals)`
        }
      }
    },
    scales: {
      x: { grid: { color: 'rgba(148,163,184,0.12)' }, ticks: { font: { size: 12 } as any, color: '#64748b' } },
      y: { grid: { color: 'rgba(148,163,184,0.12)' }, ticks: { font: { size: 12 } as any, color: '#64748b', callback: (v) => '₹' + Number(v).toLocaleString('en-IN') } }
    },
    animation: { duration: 800 } as any
  };

  // Image modal
  showImageModal = false;
  currentImageIndex = 0;
  
  // Lead capture / Content unlock
  isContentUnlocked = false;
  leadForm = {
    name: '',
    email: '',
    mobile: '',
    areaOfInterest: ''
  };
  submittingLead = false;
  leadError = '';
  deviceFingerprint = '';

  // ── Math CAPTCHA ─────────────────────────────────────────────────────────
  captchaA = 0;
  captchaB = 0;
  captchaAnswer: number | string | null = null;

  refreshCaptcha() {
    this.captchaA = Math.floor(Math.random() * 9) + 1;
    this.captchaB = Math.floor(Math.random() * 9) + 1;
    this.captchaAnswer = null;
  }

  // ── Floor Plans ───────────────────────────────────────────────────────────
  floorPlans: any[] = [];
  floorPlansLoading = false;
  floorPlansLoaded = false;
  fpModalOpen = false;
  fpModalDocName = '';
  fpModalPages: string[] = [];
  fpModalIndex = 0;
  
  // Note: Once a user submits their details for ANY property,
  // ALL properties are unlocked using:
  // 1. Backend email check (primary - most reliable)
  // 2. Device fingerprint (secondary - persists across browser clears)
  // 3. localStorage (tertiary - immediate UX)
  
  // Review form data
  reviewForm = {
    name: '',
    email: '',
    contact: '',
    rating: 5,
    review: ''
  };

  submittingReview = false;
  reviewError = '';
  reviewSuccess = '';

  // Review captcha (separate from the unlock-modal captcha)
  reviewCaptchaA: number = 0;
  reviewCaptchaB: number = 0;
  reviewCaptchaAnswer: number | string | null = null;

  refreshReviewCaptcha() {
    this.reviewCaptchaA = Math.floor(Math.random() * 9) + 1;
    this.reviewCaptchaB = Math.floor(Math.random() * 9) + 1;
    this.reviewCaptchaAnswer = null;
  }
  
  projectFields = [
    { key: 'Project Status', label: 'Status' },
    { key: 'Project Type', label: 'Type' },
    { key: 'Approved Date', label: 'Approved Date' },
    { key: 'Proposed Date of Completion', label: 'Completion Date' },
    { key: 'Revised Proposed Date of Completion', label: 'Revised Completion Date' }
  ];

  developerFields = [
    { key: 'Name', label: 'Developer Name' },
    { key: 'Organization Type', label: 'Organization Type' },
    { key: 'Do you have any Past Experience ?', label: 'Past Experience' },
    { key: 'Any criminal or police case/ cases pending ?', label: 'Criminal/Police Case Pending' }
  ];

  landFields = [
    { key: 'Total Area(In sqmts)', label: 'Total Area (sqmts)' },
    { key: 'Net Area(In sqmts)', label: 'Net Area (sqmts)' },
    { key: 'Approved Built up Area (In Sqmts)', label: 'Built up Area (sqmts)' },
    { key: 'Mortgage Area (In Sqmts)', label: 'Mortgage Area (sqmts)' },
    { key: 'Sy.No/TS No.', label: 'Survey No/TS No.' },
    { key: 'Boundaries East', label: 'East Boundary' },
    { key: 'Boundaries West', label: 'West Boundary' },
    { key: 'Boundaries North', label: 'North Boundary' },
    { key: 'Boundaries South', label: 'South Boundary' }
  ];

  bankFields = [
    { key: 'Bank Name', label: 'Bank Name' },
    { key: 'Branch Name', label: 'Branch Name' },
    { key: 'IFSC Code', label: 'IFSC Code' }
  ];

  locationFields = [
    { key: 'State', label: 'State' },
    { key: 'District', label: 'District' },
    { key: 'Mandal', label: 'Mandal' },
    { key: 'Village/City/Town', label: 'Village/City/Town' },
    { key: 'Pin Code', label: 'Pin Code' },
    { key: 'Street', label: 'Street' },
    { key: 'Locality', label: 'Locality' },
    { key: 'Land mark', label: 'Landmark' },
    { key: 'Authority Name', label: 'Authority Name' },
    { key: 'Plan Approval Number', label: 'Plan Approval Number' }
  ];

  legalFields = [
    { key: 'Litigations related to the project ?', label: 'Litigation Status' },
    { key: 'Any criminal or police case/ cases pending ?', label: 'Criminal/Police Cases' },
    { key: 'Are there any Promoter(Land Owner/ Investor) (as defined by Telangana RERA Order) in the project ?', label: 'Has Promoters/Investors' }
  ];

  constructor(
    private route: ActivatedRoute,
    private service: PropertyService,
    private router: Router,
    private loadingService: LoadingService,
    private favoriteService: FavoriteService,
    public auth: AuthService,
    private userData: UserDataService,
    private mediaService: MediaService
  ) {}

  ngOnInit(): void {
    // Scroll to top of page
    window.scrollTo(0, 0);
    
    const id = this.route.snapshot.paramMap.get('id');
    if (id) {
      this.loading = true;
      
      // Ensure loading overlay shows for minimum duration
      const minimumLoadingTime = 1500; // milliseconds - longer, smoother experience
      const startTime = Date.now();
      
      // Generate device fingerprint
      this.deviceFingerprint = this.generateDeviceFingerprint();
      // Generate initial captcha challenge
      this.refreshCaptcha();
      
      this.service.getPropertyById(id).subscribe({
        next: (prop) => {
          this.property = prop;
          this.averageRating = prop.averageRating || 0;
          this.loading = false;

          // Synchronize favorite state for current property
          const propId = this.getItemId(prop);
          this.isFavorite = this.favoriteService.isFavorite(propId);
          this.favSub?.unsubscribe();
          this.favSub = this.favoriteService.favorites$.subscribe(() => {
            this.isFavorite = this.favoriteService.isFavorite(propId);
          });

          // Check saved-property state from API if logged in
          if (this.auth.isLoggedIn() && propId) {
            this.userData.isPropertySaved(propId).pipe(catchError(() => of({ exists: false }))).subscribe(r => {
              this.isSaved = r.exists;
            });
          }
          
          // Calculate remaining time to meet minimum loading duration
          const elapsedTime = Date.now() - startTime;
          const remainingTime = Math.max(0, minimumLoadingTime - elapsedTime);
          
          // Hide loading overlay after minimum duration
          setTimeout(() => {
            this.loadingService.hide();
          }, remainingTime);
          
          this.checkIfUnlocked(); // Check if user has already unlocked
          
          // Load media from DB
          this.loadPropertyMedia(id);
          
          // Lock body scroll if content is locked
          if (!this.isContentUnlocked) {
            document.body.style.overflow = 'hidden';
          }
          

          // Load SRO registered transaction trend
          const pName = prop['Project Name'] || prop['projectName'] || '';
          if (pName) this.loadSroTrend(pName);
          if (pName) this.loadSroUnits(pName);
          
          // Load latest properties
          this.loadLatestProperties(id);
        },
        error: (err) => {
          console.error('Error loading property:', err);
          this.error = 'Failed to load property details';
          
          // Calculate remaining time for error case too
          const elapsedTime = Date.now() - startTime;
          const remainingTime = Math.max(0, minimumLoadingTime - elapsedTime);
          
          setTimeout(() => {
            this.loadingService.hide();
          }, remainingTime);
          
          this.loading = false;
        }
      });
      
      // Load reviews
      this.loadReviews(id);
      // Load price history for trend chart
      this.loadPriceHistory(id);
    } else {
      this.error = 'No property ID provided';
      this.loading = false;
    }
  }

  ngOnDestroy(): void {
    // Restore body scroll when component is destroyed
    document.body.style.overflow = '';
    this.favSub?.unsubscribe();
  }

  private getItemId(item: any): string {
    const id = item?.id ?? item?.projectId ?? '';
    return id ? String(id) : '';
  }

  toggleFavorite() {
    if (!this.property) return;
    const id = this.getItemId(this.property);
    if (!id) return;

    const prop = { ...this.property, id };
    this.isFavorite = this.favoriteService.toggleFavorite(prop);
  }

  toggleSaveProperty() {
    if (!this.auth.isLoggedIn()) { this.router.navigate(['/login']); return; }
    const id = this.getItemId(this.property);
    if (!id) return;

    if (this.isSaved) {
      this.userData.removeSavedProperty(id).pipe(catchError(() => of(null))).subscribe(() => {
        this.isSaved = false;
      });
    } else {
      this.savingProperty = true;
      this.userData.addSavedProperty(id, this.savePropertyNote || undefined).pipe(
        catchError(() => of(null))
      ).subscribe(() => {
        this.savingProperty = false;
        this.isSaved = true;
        this.savePropertySuccess = 'Property saved!';
        setTimeout(() => this.savePropertySuccess = '', 3000);
      });
    }
  }

  loadReviews(id: string) {
    this.service.getReviews(id).subscribe({
      next: (reviews) => {
        // Ensure reviews is an array
        this.reviews = Array.isArray(reviews) ? reviews : [];
        this.calculateAverageRating();
      },
      error: (err) => {
        console.error('Error loading reviews:', err);
        this.reviews = [];
      }
    });
  }

  loadPriceHistory(id: string) {
    this.service.getPriceHistory(id).subscribe({
      next: (history) => {
        this.priceHistory = Array.isArray(history) ? history : [];
        if (this.priceHistory.length > 1) {
          this.hasPriceHistory = true;
          this.buildPriceChart();
        }
      },
      error: () => { this.priceHistory = []; }
    });
  }

  loadSroTrend(projectName: string) {
    this.service.getSroProjectTrend(projectName).subscribe({
      next: (res) => {
        if (!res?.found || !res.quarters?.length) return;
        this.hasSroTrend = true;
        this.sroTrendQuarters = res.quarters;
        this.sroTrendMatchedApts = res.matched_apartments || [];
        this.sroTrendTotalTx = res.total_transactions || 0;
        const labels = res.quarters.map((q: any) => q.quarter);
        const points = res.quarters.map((q: any) => ({ x: q.quarter, y: q.avg_price_sqft, _count: q.count }));
        this.sroTrendChart = {
          labels,
          datasets: [{
            label: 'Avg ₹/sqft (SRO)',
            data: points,
            borderColor: '#10b981',
            backgroundColor: 'rgba(16,185,129,0.12)',
            borderWidth: 2.5,
            pointRadius: 5,
            pointBackgroundColor: '#fff',
            pointBorderColor: '#10b981',
            pointBorderWidth: 2,
            tension: 0.35,
            fill: true,
          }]
        };
      },
      error: () => { this.hasSroTrend = false; }
    });
  }

  loadSroUnits(projectName: string) {
    this.service.getSroProjectUnits(projectName).subscribe({
      next: (res) => { this.sroUnits = res; },
      error: () => { this.sroUnits = null; }
    });
  }

  loadLatestProperties(currentId: string) {
    this.loadingLatestProperties = true;
    this.service.getProperties().subscribe({
      next: (allProps) => {
        // Filter out current property and get 4 most recent ones
        const filtered = allProps
          .filter(p => this.getItemId(p) !== currentId)
          .sort((a, b) => {
            const dateA = new Date(a['Approved Date'] || a['approvedDate'] || 0).getTime();
            const dateB = new Date(b['Approved Date'] || b['approvedDate'] || 0).getTime();
            return dateB - dateA; // Most recent first
          })
          .slice(0, 4);
        this.latestProperties = filtered;
        this.loadingLatestProperties = false;
        
        // Load thumbnails for these properties
        this.loadLatestPropertyThumbnails(filtered);
      },
      error: () => {
        this.loadingLatestProperties = false;
        this.latestProperties = [];
      }
    });
  }

  private loadLatestPropertyThumbnails(props: Property[]) {
    const requests = props.map(p => {
      const id = this.getItemId(p);
      if (!id) return of([]);
      return this.mediaService.getMedia(id, 'image').pipe(catchError(() => of([])));
    });

    forkJoin(requests).subscribe(results => {
      results.forEach((mediaList, i) => {
        const id = this.getItemId(props[i]);
        if (!id) return;
        
        if (Array.isArray(mediaList) && mediaList.length > 0) {
          // Use first image from media service
          this.latestPropertyThumbnails[id] = mediaList[0].fileUrl || mediaList[0].file_url || '';
        } else {
          // Fallback to legacy media structure
          const legacyImg = (props[i] as any)?.media?.images?.[0];
          if (legacyImg) {
            this.latestPropertyThumbnails[id] = `${environment.apiUrl}/projects/${id}/media/${legacyImg}`;
          }
        }
      });
    });
  }

  getSroSoldPct(): number {
    if (!this.property?.['totalFlats'] || !this.sroUnits?.unique_flats_registered) return 0;
    return Math.min(100, Math.round((this.sroUnits.unique_flats_registered / this.property['totalFlats']) * 100));
  }

  getSroAvailableFlats(): number {
    if (!this.property?.['totalFlats'] || !this.sroUnits) return 0;
    return Math.max(0, this.property['totalFlats'] - this.sroUnits.unique_flats_registered);
  }

  // ── Latest Properties Helpers ────────────────────────────────────────────
  getPropertyThumbnail(property: Property): string {
    const id = this.getItemId(property);
    return this.latestPropertyThumbnails[id] || '';
  }

  getPropertyName(property: Property): string {
    return property['Project Name'] || property['projectName'] || 'Untitled Project';
  }

  getPropertyLocation(property: Property): string {
    const locality = property['Locality'] || property['locality'] || property['Village/City/Town'] || property['city'] || '';
    const district = property['District'] || property['district'] || '';
    if (locality && district) return `${locality}, ${district}`;
    return locality || district || 'Location not specified';
  }

  getPropertyType(property: Property): string {
    return property['Project Type'] || property['projectType'] || 'Residential';
  }

  navigateToProperty(property: Property) {
    const id = this.getItemId(property);
    if (id) {
      this.router.navigate(['/property', id]);
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  }

  buildPriceChart() {
    // Collect all unit types across all history entries
    const unitTypes = new Set<string>();
    this.priceHistory.forEach(entry => {
      const units: any[] = entry?.data?.units ?? [];
      units.forEach((u: any) => { if (u.type) unitTypes.add(u.type); });
    });
    this.allUnitTypes = [...unitTypes];

    // Build date labels (actual) + 3 projected future months
    const actualLabels = this.priceHistory.map(e =>
      new Date(e.timestamp ?? e.date).toLocaleDateString('en-IN', { month: 'short', year: 'numeric' })
    );

    // For projection: extend 3 months from last entry
    const lastDate = new Date(this.priceHistory[this.priceHistory.length - 1]?.timestamp ?? Date.now());
    const projLabels = [1, 2, 3].map(m => {
      const d = new Date(lastDate);
      d.setMonth(d.getMonth() + m);
      return d.toLocaleDateString('en-IN', { month: 'short', year: 'numeric' });
    });
    const allLabels = [...actualLabels, ...projLabels];

    const palette = [
      { solid: '#3b82f6', fill: 'rgba(59,130,246,0.12)' },
      { solid: '#f59e0b', fill: 'rgba(245,158,11,0.12)' },
      { solid: '#10b981', fill: 'rgba(16,185,129,0.12)' },
      { solid: '#ef4444', fill: 'rgba(239,68,68,0.12)' },
      { solid: '#8b5cf6', fill: 'rgba(139,92,246,0.12)' },
      { solid: '#ec4899', fill: 'rgba(236,72,153,0.12)' }
    ];
    const datasets: any[] = [];
    this.priceStats = [];

    [...unitTypes].forEach((type, idx) => {
      const { solid: color, fill: fillColor } = palette[idx % palette.length];

      // Actual data points
      const actualPoints = this.priceHistory.map(e => {
        const units: any[] = e?.data?.units ?? [];
        const u = units.find((x: any) => x.type === type);
        return u ? Number(u.pricePerSqft) : null;
      });

      // Compute stats
      const validPoints = actualPoints.filter(v => v !== null) as number[];
      if (validPoints.length >= 1) {
        const first = validPoints[0];
        const last = validPoints[validPoints.length - 1];
        const change = last - first;
        const changePct = first > 0 ? Math.round((change / first) * 1000) / 10 : 0;
        this.priceStats.push({ type, current: last, change, changePct, color });
      }

      // Weighted linear regression (exponential weights — recent points weighted more)
      let projected: (number | null)[] = [null, null, null];
      if (validPoints.length >= 2) {
        const n = validPoints.length;
        // Weight = 2^i so the most recent point has the highest influence
        const weights = validPoints.map((_, i) => Math.pow(2, i));
        const W   = weights.reduce((a, b) => a + b, 0);
        const Wx  = weights.reduce((s, w, i) => s + w * i, 0);
        const Wy  = weights.reduce((s, w, i) => s + w * validPoints[i], 0);
        const Wxx = weights.reduce((s, w, i) => s + w * i * i, 0);
        const Wxy = weights.reduce((s, w, i) => s + w * i * validPoints[i], 0);
        const denom = W * Wxx - Wx * Wx;
        const slope = denom !== 0 ? (W * Wxy - Wx * Wy) / denom : 0;
        const intercept = (Wy - slope * Wx) / W;
        projected = [1, 2, 3].map(m => Math.max(0, Math.round(intercept + slope * (n - 1 + m))));
      }

      // Actual line with fill
      datasets.push({
        label: type,
        data: [...actualPoints, ...Array(3).fill(null)],
        borderColor: color,
        backgroundColor: fillColor,
        borderWidth: 2.5,
        tension: 0.4,
        pointRadius: 5,
        pointHoverRadius: 8,
        pointBackgroundColor: '#fff',
        pointBorderColor: color,
        pointBorderWidth: 2.5,
        fill: true,
        spanGaps: true
      });

      // Projected dashed line
      const lastActual = actualPoints[actualPoints.length - 1];
      datasets.push({
        label: `${type} (Projected)`,
        data: [...Array(actualPoints.length - 1).fill(null), lastActual, ...projected],
        borderColor: color,
        backgroundColor: 'transparent',
        borderDash: [7, 5],
        borderWidth: 2,
        tension: 0.4,
        pointRadius: 5,
        pointHoverRadius: 7,
        pointBackgroundColor: '#fff',
        pointBorderColor: color,
        pointBorderWidth: 2,
        pointStyle: 'triangle',
        fill: false,
        spanGaps: false
      });
    });

    this.allPriceDatasets = datasets;
    this.priceChartAllLabels = allLabels;
    this.applyUnitFilter();
  }

  selectUnitType(type: string) {
    this.selectedUnitType = type;
    this.applyUnitFilter();
  }

  private applyUnitFilter() {
    let filtered = this.allPriceDatasets;
    if (this.selectedUnitType !== 'All') {
      filtered = this.allPriceDatasets.filter(d =>
        d.label === this.selectedUnitType || d.label === `${this.selectedUnitType} (Projected)`
      );
    }
    this.priceChartData = { labels: this.priceChartAllLabels, datasets: filtered };
  }

  calculateAverageRating() {
    // Safety check to ensure reviews is an array
    if (!Array.isArray(this.reviews) || this.reviews.length === 0) {
      this.averageRating = 0;
      return;
    }
    const sum = this.reviews.reduce((acc, review) => acc + review.rating, 0);
    this.averageRating = Math.round((sum / this.reviews.length) * 10) / 10;
  }

  toggleReviewForm() {
    this.showReviewForm = !this.showReviewForm;
    if (this.showReviewForm) this.refreshReviewCaptcha();
  }

  submitReview() {
    const id = this.route.snapshot.paramMap.get('id');
    if (!id) return;
    
    // Validate form
    if (!this.reviewForm.name || !this.reviewForm.email || !this.reviewForm.contact || !this.reviewForm.review) {
      this.reviewError = 'All fields are required';
      return;
    }
    
    // Validate email
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(this.reviewForm.email)) {
      this.reviewError = 'Please enter a valid email address';
      return;
    }
    
    // Validate contact
    const contactRegex = /^[0-9]{10}$/;
    if (!contactRegex.test(this.reviewForm.contact)) {
      this.reviewError = 'Please enter a valid 10-digit contact number';
      return;
    }
    
    this.submittingReview = true;
    this.reviewError = '';
    this.reviewSuccess = '';
    
    this.service.addReview(id, this.reviewForm).subscribe({
      next: (response) => {
        this.reviewSuccess = 'Your review has been submitted successfully!';
        this.submittingReview = false;
        this.showReviewForm = false;
        
        // Reset form
        this.reviewForm = {
          name: '',
          email: '',
          contact: '',
          rating: 5,
          review: ''
        };
        this.refreshReviewCaptcha();
        
        // Reload reviews
        this.loadReviews(id);
        
        // Clear success message after 5 seconds
        setTimeout(() => {
          this.reviewSuccess = '';
        }, 5000);
      },
      error: (err) => {
        this.reviewError = err.error?.message || 'Error submitting review. Please try again.';
        this.submittingReview = false;
      }
    });
  }

  getStarArray(rating: number): boolean[] {
    return Array(5).fill(false).map((_, i) => i < rating);
  }

  setRating(rating: number) {
    this.reviewForm.rating = rating;
  }

  formatArea(area: string | undefined): string {
    if (!area) return 'N/A';
    const num = parseFloat(area);
    if (isNaN(num)) return area;
    return num.toLocaleString('en-IN', { maximumFractionDigits: 2 }) + ' sq.m';
  }

  getMembers(): any[] {
    if (!this.property) return [];
    const members = this.property['Member Information'];
    return Array.isArray(members) ? members : [];
  }

  getPlotDetails(): any[] {
    if (!this.property) return [];
    const plots = this.property['Plot Details'];
    return Array.isArray(plots) ? plots : [];
  }

  getDevelopmentWork(): any[] {
    if (!this.property) return [];
    const work = this.property['Development Work'];
    return Array.isArray(work) ? work : [];
  }

  getProfessionals(): any[] {
    if (!this.property) return [];
    const professionals = this.property['Project Professional Information'];
    return Array.isArray(professionals) ? professionals : [];
  }

  getFloorBreakdown(): any[] {
    if (!this.property) return [];
    const rows = this.property['Floor Breakdown'];
    return Array.isArray(rows) ? rows : [];
  }

  getBuildingTowerDetails(): any[] {
    if (!this.property) return [];
    const rows = this.property['Building Tower Details'];
    if (!Array.isArray(rows)) return [];
    // Filter out any junk rows that slipped through (blob values, floor-breakdown rows, construction-progress rows)
    return rows.filter((t: any) => {
      const name: string = (t['Name'] || '').toLowerCase();
      if (name === 'true' || name === 'false') return false;
      if (name.includes('floor id') || name.includes('saleable area') || name.includes('mortgage area')) return false;
      // Drop construction-progress task rows whose Name is a bare number (e.g. "100" = percentage)
      if (/^\d+(\.\d+)?$/.test(name)) return false;
      if (Object.values(t).some((v: any) => typeof v === 'string' && v.length > 200)) return false;
      return true;
    });
  }

  getMaxFloors(): number {
    const towers = this.getBuildingTowerDetails();
    if (!towers.length) return 0;
    return towers.reduce((max, t) => {
      const slabs = parseInt(t['Number of Slab of Super Structure'] || '0', 10);
      return slabs > max ? slabs : max;
    }, 0);
  }

  getTowerCount(): number {
    return this.getBuildingTowerDetails().length;
  }

  getDocuments(): any {
    if (!this.property) return {};
    const docs = this.property['Uploaded Documents'];
    return (docs && typeof docs === 'object' && !Array.isArray(docs)) ? docs : {};
  }

  hasDocuments(): boolean {
    const docs = this.getDocuments();
    return docs && Object.keys(docs).length > 0;
  }

  allDocsExpanded = false;

  private get _fpHeroEntry(): any {
    const priority = ['building-plan', 'floor-plan', 'layout-plan'];
    for (const key of priority) {
      const match = this.floorPlans.find((e: any) => e.label?.includes(key));
      if (match) return match;
    }
    // fallback: any doc that isn't a cert/letter
    const nonCert = this.floorPlans.find((e: any) => !e.label?.includes('cert') && !e.label?.includes('letter'));
    return nonCert || this.floorPlans[0];
  }

  get fpHeroImage(): string { return this._fpHeroEntry?.pages[0] || ''; }
  get fpHeroDocName(): string { return this._fpHeroEntry?.docName || 'Floor Plan'; }
  get fpHeroEntry(): any { return this._fpHeroEntry; }
  get fpTotalPages(): number { return this.floorPlans.reduce((s: number, e: any) => s + e.pages.length, 0); }

  loadFloorPlans(): void {
    if (this.floorPlansLoaded || !this.property?.id) return;
    this.floorPlansLoading = true;
    this.allDocsExpanded = false;
    this.service.getFloorPlans(this.property.id).subscribe({
      next: (data) => {
        this.floorPlans = data || [];
        this.floorPlansLoading = false;
        this.floorPlansLoaded = true;
      },
      error: () => {
        this.floorPlansLoading = false;
        this.floorPlansLoaded = true;
      }
    });
  }

  fpScale = 1;
  get fpZoomPct(): number { return Math.round(this.fpScale * 100); }

  openFloorPlanModal(docName: string, index: number, pages: string[]): void {
    this.fpModalDocName = docName;
    this.fpModalPages = pages;
    this.fpModalIndex = index;
    this.fpScale = 1;
    this.fpModalOpen = true;
  }

  closeFpModal(): void { this.fpModalOpen = false; this.fpScale = 1; }
  fpPrev(): void { if (this.fpModalIndex > 0) { this.fpModalIndex--; this.fpScale = 1; } }
  fpNext(): void { if (this.fpModalIndex < this.fpModalPages.length - 1) { this.fpModalIndex++; this.fpScale = 1; } }
  fpGoTo(i: number): void { this.fpModalIndex = i; this.fpScale = 1; }
  fpZoomIn(): void  { this.fpScale = Math.min(5, parseFloat((this.fpScale + 0.25).toFixed(2))); }
  fpZoomOut(): void { this.fpScale = Math.max(0.25, parseFloat((this.fpScale - 0.25).toFixed(2))); }
  fpZoomReset(): void { this.fpScale = 1; }

  onFpWheel(e: WheelEvent): void {
    e.preventDefault();
    if (e.deltaY < 0) this.fpZoomIn(); else this.fpZoomOut();
  }

  getTotalPlots(): number {
    const plots = this.getPlotDetails();
    if (!plots || plots.length === 0) return 0;
    return plots.reduce((sum, plot) => sum + parseInt(plot['Proposed Number of Plots'] || '0'), 0);
  }

  getBookedPlots(): number {
    const plots = this.getPlotDetails();
    if (!plots || plots.length === 0) return 0;
    return plots.reduce((sum, plot) => sum + parseInt(plot['Number of Plots Booked / Alloted / Sold'] || '0'), 0);
  }

  getAvailablePlots(): number {
    return this.getTotalPlots() - this.getBookedPlots();
  }

  getCompletionPercentage(percent: string): number {
    return parseInt(percent || '0');
  }

  isDocumentAvailable(value: string): boolean {
    return value === 'View' || value.includes('View');
  }

  downloadDocument(docName: string) {
    // RERA scraped docs: value is 'View' with no mediaId — open RERA portal
    // DB-backed documents: use the media download endpoint
    const matchingDbDoc = this.propertyDocuments.find(
      d => (d.title || '').toLowerCase() === docName.toLowerCase()
    );

    if (matchingDbDoc) {
      const mediaId = (matchingDbDoc as any).id || (matchingDbDoc as any).mediaId;
      const projectId = this.property?.id;
      if (mediaId && projectId) {
        this.service.downloadDocument(projectId, mediaId).subscribe({
          next: (blob) => {
            const ext = this.getExtensionFromMime((matchingDbDoc as any).mimeType || (matchingDbDoc as any).mime_type || '');
            const fileName = docName + (docName.includes('.') ? '' : ext);
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = fileName;
            a.click();
            window.URL.revokeObjectURL(url);
          },
          error: () => alert(`Failed to download "${docName}". Please try again.`)
        });
        return;
      }
    }

    // Fallback: open raw URL if available
    const docs = this.getDocuments();
    const docEntry = docs[docName];
    if (docEntry && typeof docEntry === 'string' && docEntry.startsWith('http')) {
      window.open(docEntry, '_blank');
    } else {
      alert(`Document "${docName}" is not available for download.`);
    }
  }

  private getExtensionFromMime(mime: string): string {
    const map: Record<string, string> = {
      'application/pdf': '.pdf',
      'application/msword': '.doc',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
      'image/jpeg': '.jpg',
      'image/png': '.png',
    };
    return map[mime] || '';
  }

  // ── Schedule Visit ───────────────────────────────────────────────────────
  showScheduleVisitForm = false;
  showEnquiryModal = false;
  
  scheduleVisitForm = {
    name: '',
    email: '',
    mobile: '',
    visitDate: '',
    visitTime: '',
    message: '',
    locationAddress: '',
    locationLat: null as number | null,
    locationLng: null as number | null,
    locationMapUrl: ''
  };
  submittingVisit = false;
  visitError = '';
  visitSuccess = '';

  // Visit captcha (separate from unlock captcha)
  visitCaptchaA = 0;
  visitCaptchaB = 0;
  visitCaptchaAnswer: number | string | null = null;

  // OSM location search
  visitLocationQuery = '';
  locationSuggestions: any[] = [];
  locationSuggestionIndex = -1;
  locationSearching = false;
  private _locationDebounce: any = null;

  refreshVisitCaptcha() {
    this.visitCaptchaA = Math.floor(Math.random() * 9) + 1;
    this.visitCaptchaB = Math.floor(Math.random() * 9) + 1;
    this.visitCaptchaAnswer = null;
  }

  onLocationInput() {
    const q = this.visitLocationQuery.trim();
    this.locationSuggestions = [];
    this.locationSuggestionIndex = -1;
    this.scheduleVisitForm.locationAddress = '';
    this.scheduleVisitForm.locationLat = null;
    this.scheduleVisitForm.locationLng = null;
    this.scheduleVisitForm.locationMapUrl = '';

    if (q.length < 3) return;

    clearTimeout(this._locationDebounce);
    this._locationDebounce = setTimeout(() => {
      this.locationSearching = true;
      const url = `https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(q)},+Hyderabad,+India&format=json&limit=5&addressdetails=0`;
      fetch(url, { headers: { 'Accept-Language': 'en' } })
        .then(r => r.json())
        .then((results: any[]) => {
          this.locationSuggestions = results;
          this.locationSearching = false;
        })
        .catch(() => { this.locationSearching = false; });
    }, 400);
  }

  pickLocationSuggestion(index: number) {
    const s = this.locationSuggestions[index];
    if (!s) return;
    const lat = parseFloat(s.lat);
    const lng = parseFloat(s.lon);
    this.scheduleVisitForm.locationAddress = s.display_name;
    this.scheduleVisitForm.locationLat = lat;
    this.scheduleVisitForm.locationLng = lng;
    this.scheduleVisitForm.locationMapUrl =
      `https://www.openstreetmap.org/?mlat=${lat}&mlon=${lng}#map=16/${lat}/${lng}`;
    this.visitLocationQuery = s.display_name.split(',').slice(0, 2).join(', ');
    this.locationSuggestions = [];
  }

  clearLocation() {
    this.visitLocationQuery = '';
    this.scheduleVisitForm.locationAddress = '';
    this.scheduleVisitForm.locationLat = null;
    this.scheduleVisitForm.locationLng = null;
    this.scheduleVisitForm.locationMapUrl = '';
  }

  openScheduleVisit() {
    this.showScheduleVisitForm = true;
    this.visitError = '';
    this.visitSuccess = '';
    this.refreshVisitCaptcha();
  }

  closeScheduleVisit() {
    this.showScheduleVisitForm = false;
    this.locationSuggestions = [];
  }

  submitScheduleVisit() {
    const f = this.scheduleVisitForm;

    if (!f.name || !f.email || !f.mobile || !f.visitDate || !f.visitTime) {
      this.visitError = 'Please fill all required fields';
      return;
    }

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(f.email)) {
      this.visitError = 'Please enter a valid email address';
      return;
    }

    const mobileRegex = /^\d{10}$/;
    if (!mobileRegex.test(f.mobile)) {
      this.visitError = 'Please enter a valid 10-digit mobile number';
      return;
    }

    const selectedDate = new Date(f.visitDate);
    if (selectedDate < new Date(new Date().toDateString())) {
      this.visitError = 'Visit date cannot be in the past';
      return;
    }

    if (this.visitCaptchaAnswer === null || this.visitCaptchaAnswer === '') {
      this.visitError = 'Please answer the verification question';
      return;
    }
    if (+this.visitCaptchaAnswer !== this.visitCaptchaA + this.visitCaptchaB) {
      this.visitError = 'Verification answer is incorrect. Please try again.';
      this.refreshVisitCaptcha();
      return;
    }

    this.submittingVisit = true;
    this.visitError = '';

    const payload = {
      name:              f.name,
      email:             f.email,
      mobile:            f.mobile,
      visitDate:         f.visitDate,
      visitTime:         f.visitTime,
      message:           f.message || null,
      projectId:         this.property?.id || null,
      projectName:       this.property?.['Project Name'] || null,
      locationAddress:   f.locationAddress || null,
      locationLat:       f.locationLat,
      locationLng:       f.locationLng,
      locationMapUrl:    f.locationMapUrl || null
    };

    this.service.scheduleVisit(payload).subscribe({
      next: () => {
        this.visitSuccess = 'Visit scheduled! We will contact you to confirm.';
        this.submittingVisit = false;
        this.scheduleVisitForm = {
          name: '', email: '', mobile: '', visitDate: '', visitTime: '',
          message: '', locationAddress: '', locationLat: null, locationLng: null, locationMapUrl: ''
        };
        this.visitLocationQuery = '';
        this.locationSuggestions = [];
        setTimeout(() => { this.showScheduleVisitForm = false; this.visitSuccess = ''; }, 4000);
      },
      error: (err) => {
        this.visitError = err.error?.message || 'Failed to schedule visit. Please try again.';
        this.submittingVisit = false;
      }
    });
  }

  get today(): string {
    return new Date().toISOString().split('T')[0];
  }

  restoreScroll() {
    document.body.style.overflow = '';
  }

  contactAgent() {
    this.showEnquiryModal = true;
  }
  
  closeEnquiryModal() {
    this.showEnquiryModal = false;
  }

  // (submitScheduleVisit defined above in the Schedule Visit block)

  formatPrice(price: number): string {
    if (price >= 10000000) {
      return (price / 10000000).toFixed(2) + ' Cr';
    } else if (price >= 100000) {
      return (price / 100000).toFixed(2) + ' L';
    } else {
      return price.toLocaleString('en-IN');
    }
  }

  back() {
    this.router.navigate(['/']);
  }

  // Media-related methods
  hasBrochureOrImages(): boolean {
    if (!this.property || !this.property.media) return false;
    return !!(this.property.media.brochure || (this.property.media.images && this.property.media.images.length > 0));
  }

  getLocation(): string {
    if (!this.property) return '';
    const parts = [
      this.property['Locality']         || this.property['locality']           || '',
      this.property['Village/City/Town'] || this.property['city']               || '',
      this.property['District']         || this.property['district']           || '',
      this.property['State']            || this.property['state']              || '',
    ];
    return parts.filter(p => p && p.trim()).join(', ') || 'Location not available';
  }

  getBrochure(): string | null {
    return this.property?.media?.brochure || null;
  }

  getImages(): string[] {
    if (!this.property || !this.property.media || !this.property.media.images) {
      return [];
    }
    return Array.isArray(this.property.media.images) ? this.property.media.images : [];
  }

  getBrochureUrl(): string {
    const brochure = this.getBrochure();
    if (brochure && this.property) {
      return `/api/projects/${this.property.id}/media/${brochure}`;
    }
    return '#';
  }

  getImageUrl(imageName: string): string {
    if (this.property && imageName) {
      return `/api/projects/${this.property.id}/media/${imageName}`;
    }
    return '';
  }

  openImageModal(index: number) {
    this.currentImageIndex = index;
    this.showImageModal = true;
  }

  closeImageModal() {
    this.showImageModal = false;
  }

  nextImage() {
    // Use DB-backed images if available, otherwise fall back to legacy
    const count = this.propertyImages.length > 0 ? this.propertyImages.length : this.getImages().length;
    if (count > 0) {
      this.currentImageIndex = (this.currentImageIndex + 1) % count;
    }
  }

  previousImage() {
    const count = this.propertyImages.length > 0 ? this.propertyImages.length : this.getImages().length;
    if (count > 0) {
      this.currentImageIndex = (this.currentImageIndex - 1 + count) % count;
    }
  }

  // Lead Capture Methods
  submitLeadForm() {
    // Validate form
    if (!this.leadForm.name || !this.leadForm.email || !this.leadForm.mobile || !this.leadForm.areaOfInterest) {
      this.leadError = 'Please fill all required fields';
      return;
    }

    // Validate email
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(this.leadForm.email)) {
      this.leadError = 'Please enter a valid email address';
      return;
    }

    // Validate mobile (10 digits)
    const mobileRegex = /^[0-9]{10}$/;
    if (!mobileRegex.test(this.leadForm.mobile)) {
      this.leadError = 'Please enter a valid 10-digit mobile number';
      return;
    }

    // Validate captcha
    if (this.captchaAnswer === null || this.captchaAnswer === '') {
      this.leadError = 'Please answer the verification question';
      return;
    }
    if (+this.captchaAnswer !== this.captchaA + this.captchaB) {
      this.leadError = 'Verification answer is incorrect. Please try again.';
      this.refreshCaptcha();
      return;
    }

    this.submittingLead = true;
    this.leadError = '';

    // Prepare lead data
    const leadData = {
      ...this.leadForm,
      projectName: this.property?.['Project Name'],
      projectId: this.property?.id,
      deviceFingerprint: this.deviceFingerprint,
      timestamp: new Date().toISOString()
    };

    // Send to backend API
    this.service.submitLead(leadData).subscribe({
      next: (response) => {
        // Also store in localStorage for offline access
        const leads = JSON.parse(localStorage.getItem('propertyLeads') || '[]');
        leads.push(leadData);
        localStorage.setItem('propertyLeads', JSON.stringify(leads));

        // Mark ALL properties as unlocked after first submission
        localStorage.setItem('userHasUnlocked', 'true');
        localStorage.setItem('unlockTimestamp', Date.now().toString());
        localStorage.setItem('userDetails', JSON.stringify({
          name: this.leadForm.name,
          email: this.leadForm.email,
          mobile: this.leadForm.mobile,
          areaOfInterest: this.leadForm.areaOfInterest,
          firstUnlockDate: new Date().toISOString()
        }));

        // Unlock content
        this.isContentUnlocked = true;
        this.submittingLead = false;

        // Restore body scroll
        document.body.style.overflow = '';

      },
      error: (error) => {
        console.error('Error submitting lead:', error);
        this.leadError = error.error?.message || 'Failed to submit. Please try again.';
        this.submittingLead = false;
      }
    });
  }

  loadPropertyMedia(projectId: string): void {
    this.mediaService.getMedia(projectId).pipe(catchError(() => of([]))).subscribe(items => {
      this.propertyImages    = items.filter((m: any) => (m.mediaType || m.media_type) === 'image');
      this.propertyFloorplans = items.filter((m: any) => (m.mediaType || m.media_type) === 'floorplan');
      this.propertyDocuments = items.filter((m: any) => (m.mediaType || m.media_type) === 'document');
      this.propertyVideos    = items.filter((m: any) => (m.mediaType || m.media_type) === 'video');
      this.mediaLoaded = true;
      // Reset hero index when new images load
      this.currentImageIndex = 0;
    });
  }

  openLightbox(images: PropertyMedia[], index: number): void {
    this.lightboxImages = images;
    this.lightboxIndex = index;
    this.showImageLightbox = true;
    document.body.style.overflow = 'hidden';
  }

  closeLightbox(): void {
    this.showImageLightbox = false;
    document.body.style.overflow = '';
  }

  lightboxPrev(): void {
    this.lightboxIndex = (this.lightboxIndex - 1 + this.lightboxImages.length) % this.lightboxImages.length;
  }

  lightboxNext(): void {
    this.lightboxIndex = (this.lightboxIndex + 1) % this.lightboxImages.length;
  }

  getYouTubeEmbed(url: string): string {
    return this.mediaService.getYouTubeEmbedUrl(url);
  }

  getYouTubeThumbnail(url: string): string {
    return this.mediaService.getYouTubeThumbnail(url);
  }

  checkIfUnlocked() {
    if (!this.property?.id) return;

    // Logged-in users are always unlocked — no lead form needed
    if (this.auth.isLoggedIn()) {
      this.isContentUnlocked = true;
      document.body.style.overflow = '';
      return;
    }

    // First check localStorage for immediate UX - but be conservative
    // Only unlock if we have both the flag AND a valid timestamp from last 30 days
    const localUnlocked = localStorage.getItem('userHasUnlocked') === 'true';
    const unlockTimestamp = localStorage.getItem('unlockTimestamp');
    const thirtyDaysAgo = Date.now() - (30 * 24 * 60 * 60 * 1000);

    if (localUnlocked && unlockTimestamp && parseInt(unlockTimestamp) > thirtyDaysAgo) {
      this.isContentUnlocked = true;
      document.body.style.overflow = '';
      return;
    } else if (localUnlocked && (!unlockTimestamp || parseInt(unlockTimestamp) <= thirtyDaysAgo)) {
      // Clear stale unlock status
      localStorage.removeItem('userHasUnlocked');
      localStorage.removeItem('unlockTimestamp');
    }

    // Then check backend with device fingerprint
    this.service.checkUnlockStatus(this.deviceFingerprint).subscribe({
      next: (response: any) => {
        if (response.unlocked === true) {
          this.isContentUnlocked = true;
          localStorage.setItem('userHasUnlocked', 'true');
          localStorage.setItem('unlockTimestamp', Date.now().toString());
          document.body.style.overflow = '';
        }
      },
      error: (err) => {
      }
    });
  }

  generateDeviceFingerprint(): string {
    // Create a unique fingerprint from browser characteristics
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    let canvasFingerprint = '';
    
    if (ctx) {
      ctx.textBaseline = 'top';
      ctx.font = '14px Arial';
      ctx.fillText('fingerprint', 2, 2);
      canvasFingerprint = canvas.toDataURL().substring(0, 50);
    }
    
    const fingerprint = [
      navigator.userAgent,
      navigator.language,
      screen.width + 'x' + screen.height,
      screen.colorDepth,
      new Date().getTimezoneOffset(),
      navigator.hardwareConcurrency || 0,
      navigator.platform,
      canvasFingerprint
    ].join('|');
    
    // Simple hash function
    let hash = 0;
    for (let i = 0; i < fingerprint.length; i++) {
      const char = fingerprint.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash;
    }
    
    return Math.abs(hash).toString(36);
  }
}
