import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterModule, Routes } from '@angular/router';

import { MapViewComponent } from '../map-view/map-view.component';

const routes: Routes = [
  { path: 'map-view', component: MapViewComponent },
];

@NgModule({
  declarations: [MapViewComponent],
  imports: [
    CommonModule,
    FormsModule,
    RouterModule.forChild(routes),
  ],
})
export class MapFeatureModule {}
