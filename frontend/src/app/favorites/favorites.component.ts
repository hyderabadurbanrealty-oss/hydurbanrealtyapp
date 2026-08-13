import { Component, OnDestroy, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { Subscription } from 'rxjs';
import { FavoriteService } from '../services/favorite.service';
import { AuthService } from '../services/auth.service';
import { LoadingService } from '../services/loading.service';
import { Property } from '../map/map.component';

@Component({
  selector: 'app-favorites',
  templateUrl: './favorites.component.html',
  styleUrls: ['./favorites.component.css']
})
export class FavoritesComponent implements OnInit, OnDestroy {
  favorites: Property[] = [];
  subscription?: Subscription;
  Math = Math;

  constructor(
    public favoriteService: FavoriteService,
    public auth: AuthService,
    private router: Router,
    private loadingService: LoadingService
  ) {}

  ngOnInit(): void {
    this.subscription = this.favoriteService.favorites$.subscribe(favs => {
      this.favorites = favs;
    });
  }

  ngOnDestroy(): void {
    this.subscription?.unsubscribe();
  }

  viewDetails(property: Property) {
    const id = (property as any).id ?? (property as any).projectId;
    if (!id) return;
    this.loadingService.show();
    requestAnimationFrame(() => setTimeout(() => this.router.navigate(['/property', id]), 0));
  }

  removeFromFavorites(property: Property, event?: Event) {
    event?.stopPropagation();
    this.favoriteService.toggleFavorite(property);
  }

  clearFavorites() {
    this.favoriteService.clearFavorites();
  }

  getLocation(p: any): string {
    const locality = p['Locality'] || p['locality'] || p['Village/City/Town'] || p['Mandal'] || p['mandal'] || '';
    const district = p['District'] || p['district'] || '';
    if (locality && district) return `${locality}, ${district}`;
    return locality || district;
  }

  getType(p: any): string {
    return p['Project Type'] || p['projectType'] || '';
  }

  getStatus(p: any): string {
    return p['Project Status'] || p['projectStatus'] || '';
  }
}
