import { Component, EventEmitter, Input, OnChanges, OnDestroy, OnInit, Output, SimpleChanges } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { SearchService } from '../services/search.service';
import { Subject } from 'rxjs';
import { debounceTime, distinctUntilChanged } from 'rxjs/operators';

export interface Property {
  id: string;
  // Shortlisted fields
  'Project Name'?: string;
  'Project Status'?: string;
  'Project Type'?: string;
  'Approved Date'?: string;
  'Proposed Date of Completion'?: string;
  'Total Area(In sqmts)'?: string;
  'Net Area(In sqmts)'?: string;
  'Approved Built up Area (In Sqmts)'?: string;
  'Mortgage Area (In Sqmts)'?: string;
  'Boundaries East'?: string;
  'Boundaries West'?: string;
  'Boundaries North'?: string;
  'Boundaries South'?: string;
  'State'?: string;
  'District'?: string;
  'Mandal'?: string;
  'Village/City/Town'?: string;
  'Pin Code'?: string;
  'Street'?: string;
  'Locality'?: string;
  'Land mark'?: string;
  'Name'?: string;
  'Organization Type'?: string;
  'Do you have any Past Experience ?'?: string;
  'Any criminal or police case/ cases pending ?'?: string;
  'Authority Name'?: string;
  'Plan Approval Number'?: string;
  'Sy.No/TS No.'?: string;
  'Bank Name'?: string;
  'Branch Name'?: string;
  // Optionally, lat/lng/image for map
  lat?: number;
  lng?: number;
  image?: string;
  // Reviews & Ratings
  averageRating?: number;
  totalReviews?: number;
}

@Component({
  selector: 'app-map',
  templateUrl: './map.component.html',
  styleUrls: ['./map.component.css']
})
export class MapComponent implements OnInit, OnChanges, OnDestroy {
  @Input() properties: Property[] = [];
  @Input() pulse: boolean = false;
  @Input() searchTerm = ''; // Receive search term from parent
  @Output() pick = new EventEmitter<Property>();
  @Output() search = new EventEmitter<string>();

  searchQuery = '';
  suggestions: Property[] = [];
  showSuggestions = false;
  private autocompleteSubject = new Subject<string>();

  // ── Hero enquiry form ────────────────────────────────────────────────────
  enquiryForm = { name: '', mobile: '', interest: '' };
  enquirySubmitting = false;
  enquirySuccess = false;
  enquiryError = '';
  enquiryCaptchaA = 0;
  enquiryCaptchaB = 0;
  enquiryCaptchaAnswer: number | string | null = null;

  constructor(private searchService: SearchService, private http: HttpClient) {
    this.autocompleteSubject.pipe(
      debounceTime(200),
      distinctUntilChanged()
    ).subscribe(query => {
      this.updateSuggestions(query);
    });
    this.refreshEnquiryCaptcha();
  }

  ngOnInit(): void {
    // no-op
  }

  // Trigger the count-pop CSS class when stats update
  statsUpdated = false;

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['searchTerm'] && !changes['searchTerm'].firstChange) {
      this.searchQuery = this.searchTerm;
    }
    if (changes['properties'] && !changes['properties'].firstChange && this.properties.length > 0) {
      this.statsUpdated = false;
      setTimeout(() => { this.statsUpdated = true; }, 50);
    }
  }

  // ── Live stats derived from properties input ──────────────────────────────
  get totalProjects(): number {
    return this.properties.length;
  }

  get districtCount(): number {
    const districts = new Set<string>();
    this.properties.forEach(p => {
      const d = p['District'];
      if (d) districts.add(d.trim().toLowerCase());
    });
    return districts.size || 0;
  }

  public focusOn(_: Property) {
    // no-op — map disabled
  }

  onSearchInput(event: any) {
    const query = event.target.value.trim();
    this.searchQuery = query;

    // Emit search immediately for filtering
    this.search.emit(this.searchQuery);

    // Debounced autocomplete
    if (query.length >= 2) {
      this.autocompleteSubject.next(query);
    } else {
      this.suggestions = [];
      this.showSuggestions = false;
    }
  }

  private updateSuggestions(query: string) {
    if (query.length >= 2) {
      console.time('Autocomplete Time');
      this.suggestions = this.searchService.getSuggestions(query, 8);
      console.timeEnd('Autocomplete Time');
      this.showSuggestions = this.suggestions.length > 0;
    } else {
      this.suggestions = [];
      this.showSuggestions = false;
    }
  }

  selectSuggestion(property: Property) {
    this.searchQuery = property['Project Name'] || '';
    this.showSuggestions = false;
    // Emit search to update featured section filter
    this.search.emit(this.searchQuery);
    this.pick.emit(property);
    // Scroll to property card
    setTimeout(() => {
      const element = document.getElementById('featured');
      element?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 100);
  }

  performSearch() {
    if (this.searchQuery.trim()) {
      this.search.emit(this.searchQuery);
      this.showSuggestions = false;
      // Scroll to featured section
      setTimeout(() => {
        const element = document.getElementById('featured');
        element?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 100);
    }
  }

  quickFilter(type: string) {
    this.searchQuery = type;
    this.search.emit(type);
    // Scroll to featured section
    setTimeout(() => {
      const element = document.getElementById('featured');
      element?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 100);
  }

  closeSuggestions() {
    setTimeout(() => {
      this.showSuggestions = false;
    }, 200);
  }

  clearSearch() {
    this.searchQuery = '';
    this.suggestions = [];
    this.showSuggestions = false;
    this.search.emit('');
  }

  // ── Enquiry form ──────────────────────────────────────────────────────────
  refreshEnquiryCaptcha(): void {
    this.enquiryCaptchaA = Math.floor(Math.random() * 9) + 1;
    this.enquiryCaptchaB = Math.floor(Math.random() * 9) + 1;
    this.enquiryCaptchaAnswer = null;
  }

  get enquiryCaptchaValid(): boolean {
    return this.enquiryCaptchaAnswer !== null &&
           this.enquiryCaptchaAnswer !== '' &&
           +this.enquiryCaptchaAnswer === this.enquiryCaptchaA + this.enquiryCaptchaB;
  }

  submitEnquiry(): void {
    this.enquiryError = '';

    if (!this.enquiryForm.name.trim() || !this.enquiryForm.mobile.trim()) {
      this.enquiryError = 'Name and mobile number are required.';
      return;
    }
    if (!/^\d{10}$/.test(this.enquiryForm.mobile.trim())) {
      this.enquiryError = 'Enter a valid 10-digit mobile number.';
      return;
    }
    if (!this.enquiryCaptchaValid) {
      this.enquiryError = 'Please answer the verification question correctly.';
      return;
    }

    this.enquirySubmitting = true;
    this.http.post('/api/submit_lead', {
      name:           this.enquiryForm.name.trim(),
      mobile:         this.enquiryForm.mobile.trim(),
      areaOfInterest: this.enquiryForm.interest.trim() || 'General Enquiry',
      email:          '',
      source:         'hero-enquiry-form'
    }).subscribe({
      next: () => {
        this.enquirySubmitting = false;
        this.enquirySuccess = true;
        this.enquiryForm = { name: '', mobile: '', interest: '' };
        this.refreshEnquiryCaptcha();
      },
      error: () => {
        this.enquirySubmitting = false;
        this.enquiryError = 'Could not submit. Please try again or call us directly.';
      }
    });
  }

  ngOnDestroy(): void {
    // no-op
  }
}
