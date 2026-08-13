import {
  Component, Input, Output, EventEmitter, OnInit, OnDestroy
} from '@angular/core';
import { PropertyService } from '../services/property.service';

@Component({
  selector: 'app-schedule-visit-modal',
  templateUrl: './schedule-visit-modal.component.html',
  styleUrls: ['./schedule-visit-modal.component.css']
})
export class ScheduleVisitModalComponent implements OnInit, OnDestroy {
  @Input() projectName = '';
  @Input() projectId   = '';
  @Output() closed     = new EventEmitter<void>();

  // ── Form state ────────────────────────────────────────────────────
  form = {
    name: '', email: '', mobile: '',
    visitDate: '', visitTime: '', message: '',
    locationAddress: '', locationLat: null as number | null,
    locationLng: null as number | null, locationMapUrl: ''
  };

  submitting = false;
  error      = '';
  success    = '';

  // ── Captcha ───────────────────────────────────────────────────────
  captchaA = 0;
  captchaB = 0;
  captchaAnswer: number | string | null = null;

  // ── Location search ───────────────────────────────────────────────
  locationQuery          = '';
  locationSuggestions:   any[] = [];
  locationSuggestionIdx  = -1;
  locationSearching      = false;
  private _locDebounce: any;

  get today(): string {
    return new Date().toISOString().split('T')[0];
  }

  constructor(private svc: PropertyService) {}

  ngOnInit(): void {
    this.refreshCaptcha();
    // Prevent body scroll while modal is open
    document.body.style.overflow = 'hidden';
  }

  ngOnDestroy(): void {
    document.body.style.overflow = '';
    clearTimeout(this._locDebounce);
  }

  // ── Captcha ───────────────────────────────────────────────────────
  refreshCaptcha(): void {
    this.captchaA = Math.floor(Math.random() * 9) + 1;
    this.captchaB = Math.floor(Math.random() * 9) + 1;
    this.captchaAnswer = null;
  }

  // ── Location ──────────────────────────────────────────────────────
  onLocationInput(): void {
    const q = this.locationQuery.trim();
    this.locationSuggestions = [];
    this.locationSuggestionIdx = -1;
    this._clearLocationFields();

    if (q.length < 3) return;

    clearTimeout(this._locDebounce);
    this._locDebounce = setTimeout(() => {
      this.locationSearching = true;
      const url = `https://nominatim.openstreetmap.org/search` +
        `?q=${encodeURIComponent(q)},+Hyderabad,+India&format=json&limit=5&addressdetails=0`;
      fetch(url, { headers: { 'Accept-Language': 'en' } })
        .then(r => r.json())
        .then((results: any[]) => {
          this.locationSuggestions = results;
          this.locationSearching = false;
        })
        .catch(() => { this.locationSearching = false; });
    }, 400);
  }

  pickSuggestion(i: number): void {
    const s = this.locationSuggestions[i];
    if (!s) return;
    const lat = parseFloat(s.lat);
    const lng = parseFloat(s.lon);
    this.form.locationAddress = s.display_name;
    this.form.locationLat     = lat;
    this.form.locationLng     = lng;
    this.form.locationMapUrl  =
      `https://www.openstreetmap.org/?mlat=${lat}&mlon=${lng}#map=16/${lat}/${lng}`;
    this.locationQuery = s.display_name.split(',').slice(0, 2).join(', ');
    this.locationSuggestions = [];
  }

  clearLocation(): void {
    this.locationQuery = '';
    this._clearLocationFields();
  }

  private _clearLocationFields(): void {
    this.form.locationAddress = '';
    this.form.locationLat     = null;
    this.form.locationLng     = null;
    this.form.locationMapUrl  = '';
  }

  // ── Submit ────────────────────────────────────────────────────────
  submit(): void {
    const f = this.form;
    this.error = '';

    if (!f.name || !f.email || !f.mobile || !f.visitDate || !f.visitTime) {
      this.error = 'Please fill all required fields'; return;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(f.email)) {
      this.error = 'Please enter a valid email address'; return;
    }
    if (!/^\d{10}$/.test(f.mobile)) {
      this.error = 'Please enter a valid 10-digit mobile number'; return;
    }
    if (new Date(f.visitDate) < new Date(new Date().toDateString())) {
      this.error = 'Visit date cannot be in the past'; return;
    }
    if (this.captchaAnswer === null || this.captchaAnswer === '') {
      this.error = 'Please answer the verification question'; return;
    }
    if (+this.captchaAnswer !== this.captchaA + this.captchaB) {
      this.error = 'Verification answer is incorrect.';
      this.refreshCaptcha(); return;
    }

    this.submitting = true;

    const payload = {
      name: f.name, email: f.email, mobile: f.mobile,
      visitDate: f.visitDate, visitTime: f.visitTime,
      message: f.message || null,
      projectId: this.projectId || null,
      projectName: this.projectName || null,
      locationAddress: f.locationAddress || null,
      locationLat: f.locationLat, locationLng: f.locationLng,
      locationMapUrl: f.locationMapUrl || null
    };

    this.svc.scheduleVisit(payload).subscribe({
      next: () => {
        this.success = 'Visit scheduled! We will contact you to confirm.';
        this.submitting = false;
        // Reset form
        this.form = {
          name: '', email: '', mobile: '', visitDate: '', visitTime: '', message: '',
          locationAddress: '', locationLat: null, locationLng: null, locationMapUrl: ''
        };
        this.locationQuery = '';
        this.locationSuggestions = [];
        setTimeout(() => this.close(), 4000);
      },
      error: (err) => {
        this.error = err.error?.message || 'Failed to schedule visit. Please try again.';
        this.submitting = false;
      }
    });
  }

  close(): void {
    this.closed.emit();
  }

  // Keyboard navigation for location suggestions
  onLocKeydown(event: KeyboardEvent): void {
    if (event.key === 'ArrowDown') {
      this.locationSuggestionIdx = Math.min(
        this.locationSuggestionIdx + 1, this.locationSuggestions.length - 1);
    } else if (event.key === 'ArrowUp') {
      this.locationSuggestionIdx = Math.max(this.locationSuggestionIdx - 1, 0);
    } else if (event.key === 'Enter') {
      this.pickSuggestion(this.locationSuggestionIdx);
    } else if (event.key === 'Escape') {
      this.locationSuggestions = [];
    }
  }
}
