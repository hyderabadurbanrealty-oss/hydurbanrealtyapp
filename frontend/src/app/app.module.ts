import { NgModule } from '@angular/core';
import { BrowserModule } from '@angular/platform-browser';
import { CommonModule } from '@angular/common';
import { FormsModule, ReactiveFormsModule } from '@angular/forms';
import { RouterModule, Routes, PreloadAllModules } from '@angular/router';
import { HttpClientModule, HTTP_INTERCEPTORS } from '@angular/common/http';
import { NgChartsModule } from 'ng2-charts';

import { AppComponent } from './app.component';
import { HomeComponent } from './home/home.component';
import { MapComponent } from './map/map.component';
import { PropertyDetailComponent } from './property-detail/property-detail.component';
import { PropertiesComponent } from './properties/properties.component';
import { NeighborhoodIntelligenceComponent } from './neighborhood-intelligence/neighborhood-intelligence.component';
import { ReraComplianceComponent } from './rera-compliance/rera-compliance.component';
import { ChatbotComponent } from './chatbot/chatbot.component';
import { LoadingComponent } from './loading/loading.component';
import { SharedModule } from './shared/shared.module';

import { AuthInterceptor } from './auth.interceptor';
import { ApiUrlInterceptor } from './api-url.interceptor';
import { ZoneInterceptor } from './zone.interceptor';
import { AuthGuard } from './auth.guard';
import { AdminGuard } from './admin.guard';

const routes: Routes = [
  // ── Core shell routes (included in initial bundle) ──────────────────────
  { path: '',             component: HomeComponent },
  { path: 'properties',  component: PropertiesComponent },
  { path: 'property/:id', component: PropertyDetailComponent },

  // ── Lazy feature modules ─────────────────────────────────────────────────
  {
    path: '',
    loadChildren: () =>
      import('./auth/auth.module').then(m => m.AuthFeatureModule),
  },
  {
    path: '',
    loadChildren: () =>
      import('./user/user.module').then(m => m.UserFeatureModule),
  },
  {
    path: '',
    loadChildren: () =>
      import('./content/content.module').then(m => m.ContentFeatureModule),
  },
  {
    path: '',
    loadChildren: () =>
      import('./map-feature/map-feature.module').then(m => m.MapFeatureModule),
  },

  // ── Admin (already lazy) ─────────────────────────────────────────────────
  {
    path: 'admin',
    loadChildren: () => import('./admin/admin.module').then(m => m.AdminModule),
    canActivate: [AdminGuard],
  },
];

@NgModule({
  declarations: [
    AppComponent,
    HomeComponent,
    MapComponent,
    PropertyDetailComponent,
    PropertiesComponent,
    NeighborhoodIntelligenceComponent,
    ReraComplianceComponent,
    ChatbotComponent,
    LoadingComponent,
  ],
  imports: [
    BrowserModule,
    CommonModule,
    FormsModule,
    ReactiveFormsModule,
    SharedModule,
    RouterModule.forRoot(routes, {
      useHash: false,
      scrollPositionRestoration: 'top',
      preloadingStrategy: PreloadAllModules,
    }),
    HttpClientModule,
    NgChartsModule,
  ],
  providers: [
    { provide: HTTP_INTERCEPTORS, useClass: ApiUrlInterceptor, multi: true },
    { provide: HTTP_INTERCEPTORS, useClass: AuthInterceptor,   multi: true },
    { provide: HTTP_INTERCEPTORS, useClass: ZoneInterceptor,   multi: true },
  ],
  bootstrap: [AppComponent],
})
export class AppModule {}
