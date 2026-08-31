import { Component, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { UserDataService } from '../services/user-data.service';
import { LoadingService } from '../services/loading.service';

@Component({
  standalone: false,
  selector: 'app-saved-properties',
  templateUrl: './saved-properties.component.html',
  styleUrls: ['./saved-properties.component.css']
})
export class SavedPropertiesComponent implements OnInit {
  items: any[] = [];
  loading = true;
  error = '';
  removingId: string | null = null;

  constructor(
    private userData: UserDataService,
    private router: Router,
    private loadingService: LoadingService
  ) {}

  ngOnInit(): void {
    this.userData.getSavedProperties().subscribe({
      next: items => { this.items = items; this.loading = false; },
      error: () => { this.error = 'Failed to load saved properties.'; this.loading = false; }
    });
  }

  viewDetails(item: any): void {
    this.loadingService.show();
    requestAnimationFrame(() => setTimeout(() => this.router.navigate(['/property', item.projectId]), 0));
  }

  remove(item: any, event: Event): void {
    event.stopPropagation();
    this.removingId = item.projectId;
    this.userData.removeSavedProperty(item.projectId).subscribe({
      next: () => { this.items = this.items.filter(i => i.projectId !== item.projectId); this.removingId = null; },
      error: () => this.removingId = null
    });
  }
}
