import { Component, OnInit, OnDestroy, ChangeDetectorRef, NgZone, ViewEncapsulation } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { Subject } from 'rxjs';
import { takeUntil } from 'rxjs/operators';
import { environment } from '../../../environments/environment';

const API = environment.apiUrl;

const FEATURES = [
  'Parking Included', 'Furnished', 'Semi-Furnished',
  'Corner Unit', 'Pool View', 'Clubhouse Access', 'Gated Community'
];

const CONFIGURATIONS = [
  '1 BHK', '2 BHK', '3 BHK', '4 BHK', '4+ BHK / Penthouse', 'Villa / Independent House'
];

const AGE_OPTIONS = [
  'Under construction', 'Less than 1 year', '1-3 years',
  '3-5 years', '5-10 years', 'Above 10 years'
];

const CALLBACK_SLOTS = [
  '9:00 AM – 11:00 AM', '11:00 AM – 1:00 PM',
  '2:00 PM – 4:00 PM',  '4:00 PM – 6:00 PM',
  '6:00 PM – 8:00 PM',  'Weekends only'
];

@Component({
  standalone: false,
  selector: 'app-resale-edit',
  templateUrl: './resale-edit.component.html',
  styleUrls: [
    '../resale-submit/resale-submit.component.css',
    './resale-edit.component.css'
  ],
  encapsulation: ViewEncapsulation.None
})
export class ResaleEditComponent implements OnInit, OnDestroy {

  listingId = '';

  form = {
    ownerName:       '',
    residenceType:   'india' as 'india' | 'overseas',
    contactPhone:    '',
    contactEmail:    '',
    builderName:     '',
    projectName:     '',
    location:        '',
    configuration:   '',
    superBuiltUpArea: null as number | null,
    ageOfProperty:   '',
    expectedPrice:   null as number | null,
    callbackDate:    '',
    callbackSlot:    '',
  };

  selectedFeatures: Set<string> = new Set();

  // Existing images already stored in Supabase
  retainedImageUrls: string[] = [];
  // New files chosen by user
  newFiles: File[] = [];
  newPreviews: string[] = [];

  dragOver = false;

  locationQuery          = '';
  locationSuggestions:   any[] = [];
  locationSuggestionIdx  = -1;
  locationSearching      = false;
  private locDebounce:   any;

  pageLoading = true;   // fetching existing data
  saving      = false;  // PUT in flight
  success     = false;
  error       = '';
  loadError   = '';

  features       = FEATURES;
  configurations = CONFIGURATIONS;
  ageOptions     = AGE_OPTIONS;
  callbackSlots  = CALLBACK_SLOTS;

  private destroy$ = new Subject<void>();

  get minCallbackDate(): string {
    const d = new Date(); d.setDate(d.getDate() + 1);
    return d.toISOString().split('T')[0];
  }

  get totalImages(): number {
    return this.retainedImageUrls.length + this.newFiles.length;
  }

  constructor(
    private route: ActivatedRoute,
    private router: Router,
    private http: HttpClient,
    private cdr: ChangeDetectorRef,
    private zone: NgZone
  ) {}

  ngOnInit(): void {
    this.route.paramMap.pipe(takeUntil(this.destroy$)).subscribe(params => {
      this.listingId = params.get('id') ?? '';
      this.loadListing();
    });
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }

  loadListing(): void {
    this.pageLoading = true;
    this.loadError   = '';
    this.http.get<any>(`${API}/resale/${this.listingId}/edit`).subscribe({
      next: data => {
        this.zone.run(() => {
          this.prefill(data);
          this.pageLoading = false;
          this.cdr.markForCheck();
        });
      },
      error: err => {
        this.zone.run(() => {
          this.loadError   = err.status === 404
            ? 'Listing not found or you don\'t have permission to edit it.'
            : 'Failed to load listing. Please try again.';
          this.pageLoading = false;
          this.cdr.markForCheck();
        });
      }
    });
  }

  private prefill(data: any): void {
    // Split preferred_callback back into date + slot if stored as "date · slot"
    const [cbDate, cbSlot] = (data.preferred_callback ?? '').split(' · ');

    this.form = {
      ownerName:       data.owner_name       ?? '',
      residenceType:   data.residence_type   ?? 'india',
      contactPhone:    data.contact_phone    ?? '',
      contactEmail:    data.contact_email    ?? '',
      builderName:     data.builder_name     ?? '',
      projectName:     data.project_name     ?? '',
      location:        data.location         ?? '',
      configuration:   data.configuration    ?? '',
      superBuiltUpArea: data.super_built_up_area ?? null,
      ageOfProperty:   data.age_of_property  ?? '',
      expectedPrice:   data.expected_price   ?? null,
      callbackDate:    cbDate?.trim()         ?? '',
      callbackSlot:    cbSlot?.trim()         ?? '',
    };

    this.locationQuery = data.location ?? '';

    // Features
    this.selectedFeatures.clear();
    try {
      const feats = typeof data.features === 'string'
        ? JSON.parse(data.features) : (data.features ?? []);
      (feats as string[]).forEach(f => this.selectedFeatures.add(f));
    } catch { /* ignore */ }

    // Existing images
    try {
      const imgs = typeof data.images === 'string'
        ? JSON.parse(data.images) : (data.images ?? []);
      this.retainedImageUrls = Array.isArray(imgs) ? [...imgs] : [];
    } catch { this.retainedImageUrls = []; }
  }

  // ── Features ────────────────────────────────────────────────────────────
  toggleFeature(f: string): void {
    this.selectedFeatures.has(f)
      ? this.selectedFeatures.delete(f)
      : this.selectedFeatures.add(f);
  }
  isFeatureSelected(f: string): boolean { return this.selectedFeatures.has(f); }

  // ── Location autocomplete ────────────────────────────────────────────────
  onLocationInput(): void {
    const q = this.locationQuery.trim();
    this.locationSuggestions    = [];
    this.locationSuggestionIdx  = -1;
    this.form.location          = '';
    if (q.length < 3) return;
    clearTimeout(this.locDebounce);
    this.locDebounce = setTimeout(() => {
      this.locationSearching = true;
      const url = `https://nominatim.openstreetmap.org/search` +
        `?q=${encodeURIComponent(q)},+Hyderabad,+India&format=json&limit=6&addressdetails=0`;
      fetch(url, { headers: { 'Accept-Language': 'en' } })
        .then(r => r.json())
        .then((res: any[]) => this.zone.run(() => {
          this.locationSuggestions = res;
          this.locationSearching   = false;
          this.cdr.markForCheck();
        }))
        .catch(() => this.zone.run(() => {
          this.locationSearching = false;
          this.cdr.markForCheck();
        }));
    }, 400);
  }

  pickLocation(i: number): void {
    const s = this.locationSuggestions[i];
    if (!s) return;
    this.form.location   = s.display_name;
    this.locationQuery   = s.display_name.split(',').slice(0, 3).join(', ');
    this.locationSuggestions = [];
  }

  onLocKeydown(e: KeyboardEvent): void {
    if      (e.key === 'ArrowDown') this.locationSuggestionIdx = Math.min(this.locationSuggestionIdx + 1, this.locationSuggestions.length - 1);
    else if (e.key === 'ArrowUp')   this.locationSuggestionIdx = Math.max(this.locationSuggestionIdx - 1, 0);
    else if (e.key === 'Enter')     this.pickLocation(this.locationSuggestionIdx);
    else if (e.key === 'Escape')    this.locationSuggestions = [];
  }

  clearLocation(): void {
    this.locationQuery = '';
    this.form.location = '';
    this.locationSuggestions = [];
  }

  // ── Existing image management ────────────────────────────────────────────
  removeRetained(i: number): void { this.retainedImageUrls.splice(i, 1); }

  // ── New file upload ──────────────────────────────────────────────────────
  onFileInputChange(e: Event): void {
    const input = e.target as HTMLInputElement;
    if (input.files) this.addFiles(Array.from(input.files));
    input.value = '';
  }

  onDragOver(e: DragEvent): void { e.preventDefault(); this.dragOver = true; }
  onDragLeave(): void { this.dragOver = false; }
  onDrop(e: DragEvent): void {
    e.preventDefault(); this.dragOver = false;
    if (e.dataTransfer?.files) this.addFiles(Array.from(e.dataTransfer.files));
  }

  private addFiles(files: File[]): void {
    const allowed = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp'];
    files
      .filter(f => allowed.includes(f.type) && f.size <= 10 * 1024 * 1024)
      .slice(0, 5 - this.totalImages)
      .forEach(file => {
        this.newFiles.push(file);
        const r = new FileReader();
        r.onload = ev => this.zone.run(() => {
          this.newPreviews.push(ev.target?.result as string);
          this.cdr.markForCheck();
        });
        r.readAsDataURL(file);
      });
  }

  removeNew(i: number): void {
    this.newFiles.splice(i, 1);
    this.newPreviews.splice(i, 1);
  }

  // ── Helpers ─────────────────────────────────────────────────────────────
  formatPrice(v: number | null): string {
    if (!v) return '';
    if (v >= 10000000) return `₹${(v / 10000000).toFixed(2)} Cr`;
    if (v >= 100000)   return `₹${(v / 100000).toFixed(2)} L`;
    return `₹${v.toLocaleString('en-IN')}`;
  }

  // ── Save ─────────────────────────────────────────────────────────────────
  save(): void {
    this.error = '';
    if (!this.form.ownerName.trim())    { this.error = 'Owner name is required'; return; }
    if (!this.form.contactPhone.trim()) { this.error = 'Contact phone is required'; return; }
    if (!/^\d{10}$/.test(this.form.contactPhone.replace(/\s/g, ''))) {
      this.error = 'Enter a valid 10-digit phone number'; return;
    }

    this.saving = true;
    const fd = new FormData();
    fd.append('ownerName',          this.form.ownerName.trim());
    fd.append('residenceType',      this.form.residenceType);
    fd.append('contactPhone',       this.form.contactPhone.trim());
    fd.append('contactEmail',       this.form.contactEmail || '');
    fd.append('builderName',        this.form.builderName  || '');
    fd.append('projectName',        this.form.projectName  || '');
    fd.append('location',           this.form.location || this.locationQuery || '');
    fd.append('configuration',      this.form.configuration || '');
    fd.append('superBuiltUpArea',   this.form.superBuiltUpArea?.toString() || '');
    fd.append('ageOfProperty',      this.form.ageOfProperty || '');
    fd.append('expectedPrice',      this.form.expectedPrice?.toString() || '');
    fd.append('preferredCallback',  [this.form.callbackDate, this.form.callbackSlot].filter(Boolean).join(' · '));
    fd.append('featuresJson',       JSON.stringify(Array.from(this.selectedFeatures)));
    fd.append('retainedImagesJson', JSON.stringify(this.retainedImageUrls));
    this.newFiles.forEach(f => fd.append('newImages', f, f.name));

    this.http.put(`${API}/resale/${this.listingId}`, fd).subscribe({
      next: () => this.zone.run(() => {
        this.saving  = false;
        this.success = true;
        this.cdr.markForCheck();
      }),
      error: err => this.zone.run(() => {
        this.saving = false;
        this.error  = err?.error?.message || 'Failed to save changes. Please try again.';
        this.cdr.markForCheck();
      })
    });
  }
}
