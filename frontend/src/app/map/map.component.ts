import { Component, EventEmitter, Input, OnChanges, OnDestroy, OnInit, Output, SimpleChanges } from '@angular/core';
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

  constructor(private searchService: SearchService) {
    // Debounce autocomplete suggestions
    this.autocompleteSubject.pipe(
      debounceTime(200),
      distinctUntilChanged()
    ).subscribe(query => {
      this.updateSuggestions(query);
    });
  }

  ngOnInit(): void {
    // no-op
  }

  ngOnChanges(changes: SimpleChanges): void {
    // Sync search query when parent updates it
    if (changes['searchTerm'] && !changes['searchTerm'].firstChange) {
      this.searchQuery = this.searchTerm;
    }
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

  ngOnDestroy(): void {
    // no-op
  }
}
