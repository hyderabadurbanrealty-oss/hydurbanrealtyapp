import { Component, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { UserDataService } from '../services/user-data.service';

@Component({
  selector: 'app-saved-searches',
  templateUrl: './saved-searches.component.html',
  styleUrls: ['./saved-searches.component.css']
})
export class SavedSearchesComponent implements OnInit {
  items: any[] = [];
  loading = true;
  error = '';
  runningId: string | null = null;
  deletingId: string | null = null;

  constructor(private userData: UserDataService, private router: Router) {}

  ngOnInit(): void {
    this.userData.getSavedSearches().subscribe({
      next: items => { this.items = items; this.loading = false; },
      error: () => { this.error = 'Failed to load saved searches.'; this.loading = false; }
    });
  }

  runSearch(item: any): void {
    this.runningId = item.id;
    this.userData.runSavedSearch(item.id).subscribe({
      next: result => {
        this.runningId = null;
        // Update result count in list
        const idx = this.items.findIndex(i => i.id === item.id);
        if (idx > -1) this.items[idx].resultCount = result.resultCount;
        // Navigate to properties (saved search results could be shown there)
        this.router.navigate(['/properties']);
      },
      error: () => this.runningId = null
    });
  }

  delete(item: any): void {
    if (!confirm(`Delete search "${item.name}"?`)) return;
    this.deletingId = item.id;
    this.userData.deleteSavedSearch(item.id).subscribe({
      next: () => { this.items = this.items.filter(i => i.id !== item.id); this.deletingId = null; },
      error: () => this.deletingId = null
    });
  }

  filtersLabel(item: any): string {
    const f = item.filters ?? {};
    const parts: string[] = [];
    if (f.district) parts.push(f.district);
    if (f.projectStatus) parts.push(f.projectStatus);
    if (f.pinCodes?.length) parts.push(f.pinCodes.join(', '));
    if (f.minFlats) parts.push(`≥${f.minFlats} flats`);
    return parts.join(' · ') || 'All properties';
  }
}
