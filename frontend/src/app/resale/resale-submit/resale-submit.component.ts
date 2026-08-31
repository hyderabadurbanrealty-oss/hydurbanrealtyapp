import { Component, OnInit, ViewEncapsulation } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { AuthService } from '../../services/auth.service';
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
  '2:00 PM – 4:00 PM', '4:00 PM – 6:00 PM',
  '6:00 PM – 8:00 PM', 'Weekends only'
];

@Component({
  standalone: false,
  selector: 'app-resale-submit',
  templateUrl: './resale-submit.component.html',
  styleUrls: ['./resale-submit.component.css'],
  encapsulation: ViewEncapsulation.None
})
export class ResaleSubmitComponent implements OnInit {
  form = {
    ownerName: '',
    residenceType: 'india' as 'india' | 'overseas',
    contactPhone: '',
    contactEmail: '',
    builderName: '',
    projectName: '',
    location: '',
    locationLat: null as number | null,
    locationLng: null as number | null,
    configuration: '',
    superBuiltUpArea: null as number | null,
    ageOfProperty: '',
    expectedPrice: null as number | null,
    callbackDate: '',
    callbackSlot: '',
  };

  selectedFeatures: Set<string> = new Set();
  selectedFiles: File[] = [];
  previewUrls: string[] = [];

  loading  = false;
  success  = false;
  error    = '';
  dragOver = false;

  locationQuery         = '';
  locationSuggestions:  any[] = [];
  locationSuggestionIdx = -1;
  locationSearching     = false;
  private locDebounce: any;

  features       = FEATURES;
  configurations = CONFIGURATIONS;
  ageOptions     = AGE_OPTIONS;
  callbackSlots  = CALLBACK_SLOTS;

  get minCallbackDate(): string {
    const d = new Date();
    d.setDate(d.getDate() + 1);
    return d.toISOString().split('T')[0];
  }

  constructor(private http: HttpClient, private auth: AuthService) {}

  ngOnInit(): void {
    const user = this.auth.getCurrentUser();
    if (user) {
      this.form.ownerName    = user.fullName || '';
      this.form.contactEmail = user.email    || '';
      this.form.contactPhone = user.mobile   || '';
    }
  }

  toggleFeature(f: string): void {
    this.selectedFeatures.has(f) ? this.selectedFeatures.delete(f) : this.selectedFeatures.add(f);
  }

  isFeatureSelected(f: string): boolean { return this.selectedFeatures.has(f); }

  onLocationInput(): void {
    const q = this.locationQuery.trim();
    this.locationSuggestions = [];
    this.locationSuggestionIdx = -1;
    this.form.locationLat = null;
    this.form.locationLng = null;
    this.form.location = '';
    if (q.length < 3) return;
    clearTimeout(this.locDebounce);
    this.locDebounce = setTimeout(() => {
      this.locationSearching = true;
      const url = `https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(q)},+Hyderabad,+India&format=json&limit=6&addressdetails=0`;
      fetch(url, { headers: { 'Accept-Language': 'en' } })
        .then(r => r.json())
        .then((res: any[]) => { this.locationSuggestions = res; this.locationSearching = false; })
        .catch(() => { this.locationSearching = false; });
    }, 400);
  }

  pickLocation(i: number): void {
    const s = this.locationSuggestions[i];
    if (!s) return;
    this.form.location    = s.display_name;
    this.form.locationLat = parseFloat(s.lat);
    this.form.locationLng = parseFloat(s.lon);
    this.locationQuery    = s.display_name.split(',').slice(0, 3).join(', ');
    this.locationSuggestions = [];
  }

  onLocKeydown(e: KeyboardEvent): void {
    if (e.key === 'ArrowDown')      this.locationSuggestionIdx = Math.min(this.locationSuggestionIdx + 1, this.locationSuggestions.length - 1);
    else if (e.key === 'ArrowUp')   this.locationSuggestionIdx = Math.max(this.locationSuggestionIdx - 1, 0);
    else if (e.key === 'Enter')     this.pickLocation(this.locationSuggestionIdx);
    else if (e.key === 'Escape')    this.locationSuggestions = [];
  }

  clearLocation(): void {
    this.locationQuery = '';
    this.form.location = '';
    this.form.locationLat = null;
    this.form.locationLng = null;
    this.locationSuggestions = [];
  }

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
    files
      .filter(f => ['image/jpeg','image/jpg','image/png','image/webp'].includes(f.type) && f.size <= 10*1024*1024)
      .slice(0, 5 - this.selectedFiles.length)
      .forEach(file => {
        this.selectedFiles.push(file);
        const r = new FileReader();
        r.onload = (ev) => this.previewUrls.push(ev.target?.result as string);
        r.readAsDataURL(file);
      });
  }

  removeImage(i: number): void { this.selectedFiles.splice(i, 1); this.previewUrls.splice(i, 1); }

  formatPrice(v: number | null): string {
    if (!v) return '';
    if (v >= 10000000) return `₹${(v/10000000).toFixed(2)} Cr`;
    if (v >= 100000)   return `₹${(v/100000).toFixed(2)} L`;
    return `₹${v.toLocaleString('en-IN')}`;
  }

  submit(): void {
    this.error = '';
    if (!this.form.ownerName.trim())    { this.error = 'Owner name is required'; return; }
    if (!this.form.contactPhone.trim()) { this.error = 'Contact phone is required'; return; }
    if (!/^\d{10}$/.test(this.form.contactPhone.replace(/\s/g, ''))) {
      this.error = 'Enter a valid 10-digit phone number'; return;
    }

    this.loading = true;
    const fd = new FormData();
    fd.append('ownerName',         this.form.ownerName.trim());
    fd.append('residenceType',     this.form.residenceType);
    fd.append('contactPhone',      this.form.contactPhone.trim());
    fd.append('contactEmail',      this.form.contactEmail || '');
    fd.append('builderName',       this.form.builderName || '');
    fd.append('projectName',       this.form.projectName || '');
    fd.append('location',          this.form.location || this.locationQuery || '');
    fd.append('configuration',     this.form.configuration || '');
    fd.append('superBuiltUpArea',  this.form.superBuiltUpArea?.toString() || '');
    fd.append('ageOfProperty',     this.form.ageOfProperty || '');
    fd.append('expectedPrice',     this.form.expectedPrice?.toString() || '');
    fd.append('preferredCallback', [this.form.callbackDate, this.form.callbackSlot].filter(Boolean).join(' · '));
    fd.append('featuresJson',      JSON.stringify(Array.from(this.selectedFeatures)));
    this.selectedFiles.forEach(f => fd.append('images', f, f.name));

    const xhr = new XMLHttpRequest();
    xhr.open('POST', `${API}/resale`);
    const token = localStorage.getItem('authToken');
    if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`);
    xhr.onload = () => {
      this.loading = false;
      if (xhr.status === 201) { this.success = true; }
      else {
        try { this.error = JSON.parse(xhr.responseText).message || 'Submission failed.'; }
        catch { this.error = 'Submission failed. Please try again.'; }
      }
    };
    xhr.onerror = () => { this.loading = false; this.error = 'Network error. Please check connection.'; };
    xhr.send(fd);
  }

  resetForm(): void {
    this.form = {
      ownerName: '', residenceType: 'india', contactPhone: '', contactEmail: '',
      builderName: '', projectName: '', location: '', locationLat: null, locationLng: null,
      configuration: '', superBuiltUpArea: null, ageOfProperty: '',
      expectedPrice: null, callbackDate: '', callbackSlot: ''
    };
    this.selectedFeatures.clear();
    this.selectedFiles = []; this.previewUrls = [];
    this.success = false; this.error = '';
    this.locationQuery = ''; this.locationSuggestions = [];
  }
}
