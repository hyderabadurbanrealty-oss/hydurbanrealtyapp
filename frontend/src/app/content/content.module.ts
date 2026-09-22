import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule, ReactiveFormsModule } from '@angular/forms';
import { RouterModule, Routes } from '@angular/router';
import { NgChartsModule } from 'ng2-charts';

import { AboutComponent } from '../about/about.component';
import { PrivacyComponent } from '../privacy/privacy.component';
import { TermsComponent } from '../terms/terms.component';
import { BlogListComponent } from '../blog/blog-list/blog-list.component';
import { BlogDetailComponent } from '../blog/blog-detail/blog-detail.component';
import { SocialFeedsComponent } from '../social-feeds/social-feeds.component';
import { LoanCalculatorComponent } from '../loan-calculator/loan-calculator.component';
import { MinEmiPipe, MaxEmiPipe, MinTotalIntPipe } from '../loan-calculator/loan-calc.pipes';
import { ConsultancyComponent } from '../consultancy/consultancy.component';
import { ComparisonComponent } from '../comparison/comparison.component';
import { MarketIntelligenceComponent } from '../market-intelligence/market-intelligence.component';
import { SharedModule } from '../shared/shared.module';

const routes: Routes = [
  { path: 'about',               component: AboutComponent },
  { path: 'privacy',             component: PrivacyComponent },
  { path: 'terms',               component: TermsComponent },
  { path: 'blog',                component: BlogListComponent },
  { path: 'blog/:slug',          component: BlogDetailComponent },
  { path: 'social-feeds',        component: SocialFeedsComponent },
  { path: 'loan-calculator',     component: LoanCalculatorComponent },
  { path: 'consultancy',         component: ConsultancyComponent },
  { path: 'comparison',          component: ComparisonComponent },
  { path: 'market-intelligence', component: MarketIntelligenceComponent },
];

@NgModule({
  declarations: [
    AboutComponent,
    PrivacyComponent,
    TermsComponent,
    BlogListComponent,
    BlogDetailComponent,
    SocialFeedsComponent,
    LoanCalculatorComponent,
    MinEmiPipe,
    MaxEmiPipe,
    MinTotalIntPipe,
    ConsultancyComponent,
    ComparisonComponent,
    MarketIntelligenceComponent,
  ],
  imports: [
    CommonModule,
    FormsModule,
    ReactiveFormsModule,
    NgChartsModule,
    SharedModule,
    RouterModule.forChild(routes),
  ],
})
export class ContentFeatureModule {}
