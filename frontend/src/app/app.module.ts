import { NgModule } from '@angular/core';
import { BrowserModule } from '@angular/platform-browser';
import { CommonModule } from '@angular/common';
import { FormsModule, ReactiveFormsModule } from '@angular/forms';
import { RouterModule, Routes } from '@angular/router';
import { HttpClientModule, HTTP_INTERCEPTORS } from '@angular/common/http';
import { NgChartsModule } from 'ng2-charts';
// Silence unused environment file warnings
import { environment } from '../environments/environment';

import { AppComponent } from './app.component';
import { HomeComponent } from './home/home.component';
import { MapComponent } from './map/map.component';
import { PropertyDetailComponent } from './property-detail/property-detail.component';
import { PropertiesComponent } from './properties/properties.component';
import { ComparisonComponent } from './comparison/comparison.component';
import { NeighborhoodIntelligenceComponent } from './neighborhood-intelligence/neighborhood-intelligence.component';
import { ReraComplianceComponent } from './rera-compliance/rera-compliance.component';
import { LoginComponent } from './login.component';
import { AboutComponent } from './about/about.component';
import { ChatbotComponent } from './chatbot/chatbot.component';
import { LoadingComponent } from './loading/loading.component';
import { MarketIntelligenceComponent } from './market-intelligence/market-intelligence.component';
import { FavoritesComponent } from './favorites/favorites.component';
import { ReplacePipe } from './replace.pipe';
import { PrivacyComponent } from './privacy/privacy.component';
import { TermsComponent } from './terms/terms.component';
import { SafePipe } from './safe.pipe';

// New auth & user components
import { RegisterComponent } from './register/register.component';
import { ForgotPasswordComponent } from './forgot-password/forgot-password.component';
import { ResetPasswordComponent } from './reset-password/reset-password.component';
import { VerifyEmailComponent } from './verify-email/verify-email.component';
import { UserProfileComponent } from './user-profile/user-profile.component';
import { SavedPropertiesComponent } from './saved-properties/saved-properties.component';
import { SavedSearchesComponent } from './saved-searches/saved-searches.component';
import { MapViewComponent } from './map-view/map-view.component';
import { ScheduleVisitModalComponent } from './schedule-visit-modal/schedule-visit-modal.component';
import { SocialFeedsComponent } from './social-feeds/social-feeds.component';
import { LoanCalculatorComponent } from './loan-calculator/loan-calculator.component';
import { MinEmiPipe, MaxEmiPipe, MinTotalIntPipe } from './loan-calculator/loan-calc.pipes';
import { BlogListComponent } from './blog/blog-list/blog-list.component';
import { BlogDetailComponent } from './blog/blog-detail/blog-detail.component';
import { ResaleSubmitComponent } from './resale/resale-submit/resale-submit.component';
import { ResaleListingsComponent } from './resale/resale-listings/resale-listings.component';
import { EnquiryModalComponent } from './shared/enquiry-modal/enquiry-modal.component';

import { AuthInterceptor } from './auth.interceptor';
import { ApiUrlInterceptor } from './api-url.interceptor';
import { AuthGuard } from './auth.guard';
import { AdminGuard } from './admin.guard';

const routes: Routes = [
  { path: '', component: HomeComponent },
  { path: 'properties', component: PropertiesComponent },
  { path: 'favorites', component: FavoritesComponent },
  { path: 'comparison', component: ComparisonComponent },
  { path: 'property/:id', component: PropertyDetailComponent },
  { path: 'about', component: AboutComponent },
  { path: 'privacy', component: PrivacyComponent },
  { path: 'terms', component: TermsComponent },
  { path: 'market-intelligence', component: MarketIntelligenceComponent },
  { path: 'map-view', component: MapViewComponent },
  { path: 'social-feeds', component: SocialFeedsComponent },
  { path: 'loan-calculator', component: LoanCalculatorComponent },
  { path: 'blog', component: BlogListComponent },
  { path: 'blog/:slug', component: BlogDetailComponent },
  { path: 'resale/submit', component: ResaleSubmitComponent, canActivate: [AuthGuard] },
  { path: 'resale/my-listings', component: ResaleListingsComponent, canActivate: [AuthGuard] },

  // Auth routes (public)
  { path: 'login', component: LoginComponent },
  { path: 'register', component: RegisterComponent },
  { path: 'forgot-password', component: ForgotPasswordComponent },
  { path: 'reset-password', component: ResetPasswordComponent },
  { path: 'verify-email', component: VerifyEmailComponent },

  // Authenticated user routes
  { path: 'profile', component: UserProfileComponent, canActivate: [AuthGuard] },
  { path: 'saved-properties', redirectTo: '/favorites', pathMatch: 'full' },
  { path: 'saved-searches', component: SavedSearchesComponent, canActivate: [AuthGuard] },

  // Admin (lazy-loaded)
  { path: 'admin', loadChildren: () => import('./admin/admin.module').then(m => m.AdminModule), canActivate: [AdminGuard] }
];

@NgModule({
  declarations: [
    AppComponent,
    HomeComponent,
    MapComponent,
    PropertyDetailComponent,
    PropertiesComponent,
    FavoritesComponent,
    ComparisonComponent,
    NeighborhoodIntelligenceComponent,
    ReraComplianceComponent,
    LoginComponent,
    AboutComponent,
    PrivacyComponent,
    TermsComponent,
    ChatbotComponent,
    LoadingComponent,
    MarketIntelligenceComponent,
    ReplacePipe,
    SafePipe,
    RegisterComponent,
    ForgotPasswordComponent,
    ResetPasswordComponent,
    VerifyEmailComponent,
    UserProfileComponent,
    SavedPropertiesComponent,
    SavedSearchesComponent,
    MapViewComponent,
    ScheduleVisitModalComponent,
    SocialFeedsComponent,
    LoanCalculatorComponent,
    MinEmiPipe,
    MaxEmiPipe,
    MinTotalIntPipe,
    BlogListComponent,
    BlogDetailComponent,
    ResaleSubmitComponent,
    ResaleListingsComponent,
    EnquiryModalComponent,
  ],
  imports: [
    BrowserModule,
    CommonModule,
    FormsModule,
    ReactiveFormsModule,
    RouterModule.forRoot(routes, { useHash: false, scrollPositionRestoration: 'top' }),
    HttpClientModule,
    NgChartsModule,
  ],
  providers: [
    {
      provide: HTTP_INTERCEPTORS,
      useClass: ApiUrlInterceptor,
      multi: true
    },
    {
      provide: HTTP_INTERCEPTORS,
      useClass: AuthInterceptor,
      multi: true
    }
  ],
  bootstrap: [AppComponent]
})
export class AppModule {}
