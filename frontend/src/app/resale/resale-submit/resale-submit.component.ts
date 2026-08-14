import { Component, OnInit } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
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

@Component({
  selector: 'app-resale-submit',
  templateUrl: './resale-submit.component.html',
  styleUrls: ['./resale-submit.component.css', '../../auth-shared.css']
})
export class ResaleSubmitComponent implements OnInit {
  // Form model
  form = {
    ownerName: '',
    residenceType: 'india' as 'india' | 'overseas',
    contactPhone: '',
    contactEmail: '',
    builderName: '',
    projectName: '',
    location: '',
    configuration: '',
    superBuiltUpArea: null as number | null,
    ageOfProperty: '',
    expectedPrice: null as number | null,
    preferredCallback: '',
  };

  selectedFeatures: Set<string> = new Set();
  selectedFiles: File[] = [];
  previewUrls: string[] = [];

  // UI state
  loading   = false;
  success   = false;
  error     = '';
  dragOver  = false;

  // Options
  features       = FEATURES;
  configurations = CONFIGURATIONS;
  ageOptions     = AGE_OPTIONS;

  constructor(private http: HttpClient, private auth: AuthService) {}

  ngOnInit(): void {
    const user = this.auth.getCurrentUser();
    if (user) {
      this.form.ownerName    = user.fullName || '';
      this.form.contactEmail = user.email    || '';
      this.form.contactPhone = user.mobile   || '';
    }
  }

  toggleFeature(feature: string): void {
    if (this.selectedFeatures.has(feature)) {
      this.selectedFeatures.delete(feature);
    } else {
      this.selectedFeatures.add(feature);
    }
  }

  isFeatureSelected(feature: string): boolean {
    return this.selectedFeatures.has(feature);
  }

  // ── Image handling ───────────────────────────────────────────────
  onFileInputChange(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (input.files) this.addFiles(Array.from(input.files));
  }

  onDragOver(event: DragEvent): void {
    event.preventDefault();
    this.dragOver = true;
  }

  onDragLeave(): void { this.dragOver = false; }

  onDrop(event: DragEvent): void {
    event.preventDefault();
    this.dragOver = false;
    if (event.dataTransfer?.files) this.addFiles(Array.from(event.dataTransfer.files));
  }

  private addFiles(files: File[]): void {
    const allowed = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp'];
    const remaining = 5 - this.selectedFiles.length;
    const toAdd = files
      .filter(f => allowed.includes(f.type) && f.size <= 10 * 1024 * 1024)
      .slice(0, remaining);

    toAdd.forEach(file => {
      this.selectedFiles.push(file);
      const reader = new FileReader();
      reader.onload = (e) => this.previewUrls.push(e.target?.result as string);
      reader.readAsDataURL(file);
    });
  }

  removeImage(index: number): void {
    this.selectedFiles.splice(index, 1);
    this.previewUrls.splice(index, 1);
  }

  formatPrice(value: number | null): string {
    if (!value) return '';
    if (value >= 10000000) return `₹${(value / 10000000).toFixed(2)} Cr`;
    if (value >= 100000)   return `₹${(value / 100000).toFixed(2)} L`;
    return `₹${value.toLocaleString('en-IN')}`;
  }

  // ── Submit ───────────────────────────────────────────────────────
  submit(): void {
    this.error = '';

    if (!this.form.ownerName.trim()) { this.error = 'Owner name is required'; return; }
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
    fd.append('location',          this.form.location || '');
    fd.append('configuration',     this.form.configuration || '');
    fd.append('superBuiltUpArea',  this.form.superBuiltUpArea?.toString() || '');
    fd.append('ageOfProperty',     this.form.ageOfProperty || '');
    fd.append('expectedPrice',     this.form.expectedPrice?.toString() || '');
    fd.append('preferredCallback', this.form.preferredCallback || '');
    fd.append('featuresJson',      JSON.stringify(Array.from(this.selectedFeatures)));

    this.selectedFiles.forEach(f => fd.append('images', f, f.name));

    // Use XHR to support FormData with files (interceptors add Bearer token via HttpClient
    // but XHR needs it manually)
    const xhr = new XMLHttpRequest();
    xhr.open('POST', `${API}/resale`);
    const token = localStorage.getItem('authToken');
    if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`);

    xhr.onload = () => {
      this.loading = false;
      if (xhr.status === 201) {
        this.success = true;
      } else {
        try {
          const err = JSON.parse(xhr.responseText);
          this.error = err.message || 'Submission failed. Please try again.';
        } catch {
          this.error = 'Submission failed. Please try again.';
        }
      }
    };
    xhr.onerror = () => {
      this.loading = false;
      this.error = 'Network error. Please check your connection.';
    };
    xhr.send(fd);
  }

  resetForm(): void {
    this.form = {
      ownerName: '', residenceType: 'india', contactPhone: '', contactEmail: '',
      builderName: '', projectName: '', location: '', configuration: '',
      superBuiltUpArea: null, ageOfProperty: '', expectedPrice: null, preferredCallback: ''
    };
    this.selectedFeatures.clear();
    this.selectedFiles = [];
    this.previewUrls = [];
    this.success = false;
    this.error = '';
  }
}
