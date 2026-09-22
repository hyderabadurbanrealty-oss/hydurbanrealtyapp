import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule, ReactiveFormsModule } from '@angular/forms';
import { RouterModule, Routes } from '@angular/router';

import { UserProfileComponent } from '../user-profile/user-profile.component';
import { SavedPropertiesComponent } from '../saved-properties/saved-properties.component';
import { SavedSearchesComponent } from '../saved-searches/saved-searches.component';
import { FavoritesComponent } from '../favorites/favorites.component';
import { ResaleSubmitComponent } from '../resale/resale-submit/resale-submit.component';
import { ResaleListingsComponent } from '../resale/resale-listings/resale-listings.component';
import { SharedModule } from '../shared/shared.module';
import { AuthGuard } from '../auth.guard';

import { ResaleBrowseComponent } from '../resale/resale-browse/resale-browse.component';
import { ResaleDetailComponent } from '../resale/resale-detail/resale-detail.component';

const routes: Routes = [
  { path: 'profile',             component: UserProfileComponent,    canActivate: [AuthGuard] },
  { path: 'favorites',           component: FavoritesComponent },
  { path: 'saved-properties',    redirectTo: '/favorites',           pathMatch: 'full' },
  { path: 'saved-searches',      component: SavedSearchesComponent,  canActivate: [AuthGuard] },
  { path: 'resale',              component: ResaleBrowseComponent },
  { path: 'resale/submit',       component: ResaleSubmitComponent,   canActivate: [AuthGuard] },
  { path: 'resale/my-listings',  component: ResaleListingsComponent, canActivate: [AuthGuard] },
  { path: 'resale/:slug',        component: ResaleDetailComponent },
];

@NgModule({
  declarations: [
    UserProfileComponent,
    SavedPropertiesComponent,
    SavedSearchesComponent,
    FavoritesComponent,
    ResaleBrowseComponent,
    ResaleDetailComponent,
    ResaleSubmitComponent,
    ResaleListingsComponent,
  ],
  imports: [
    CommonModule,
    FormsModule,
    ReactiveFormsModule,
    SharedModule,
    RouterModule.forChild(routes),
  ],
})
export class UserFeatureModule {}
