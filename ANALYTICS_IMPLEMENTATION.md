# Analytics Implementation Guide

## Overview

This document describes the Google Analytics (GA4) and Google Tag Manager (GTM) implementation for Hyderabad Urban Realty.

## Configuration

### Google Tag Manager
- **Container ID**: `GTM-TGZ9ZL9K`
- **Installation**: Automatically loaded via `index.html`
- **Environment variable**: `environment.gtmId`

### Google Analytics 4
- **Measurement ID**: `G-9WEPYXSXVC`
- **Installation**: Automatically loaded via `index.html`
- **Environment variable**: `environment.ga4MeasurementId`

## Architecture

```
Application Component
        ↓
AnalyticsService (centralized tracking)
        ↓
dataLayer (window.dataLayer)
        ↓
Google Tag Manager (GTM-TGZ9ZL9K)
        ↓
Google Analytics 4 (G-9WEPYXSXVC)
```

## Files Modified/Created

### Created:
- `frontend/src/app/services/analytics.service.ts` - Centralized analytics service

### Modified:
- `frontend/src/index.html` - Added GTM and GA4 script tags
- `frontend/src/environments/environment.ts` - Added `ga4MeasurementId`
- `frontend/src/environments/environment.prod.ts` - Added `ga4MeasurementId`
- `frontend/src/app/app.component.ts` - Already integrated with analytics service

## Analytics Service Location

**Path**: `frontend/src/app/services/analytics.service.ts`

The service is injectable and available throughout the application via Angular's dependency injection.

## Usage

### Initialize in App Component

The analytics service is already initialized in `app.component.ts`:

```typescript
ngOnInit(): void {
  this.analytics.initGTM();
  this.analytics.trackPageViews();
}
```

### Track Events

Import the service in any component:

```typescript
import { AnalyticsService } from './services/analytics.service';

constructor(private analytics: AnalyticsService) {}
```

## Supported Events

### 1. Property View
```typescript
this.analytics.trackPropertyView({
  property_id: '12345',
  property_type: 'apartment',
  listing_type: 'sale',
  locality: 'Raidurg',
  city: 'Hyderabad',
  price_range: '50L-1Cr',
  bedrooms: 3
});
```

### 2. Property Search
```typescript
this.analytics.trackPropertySearch({
  search_type: 'filter',
  locality: 'Gachibowli',
  property_type: 'apartment',
  listing_type: 'rent',
  bedrooms: 2,
  price_range: '20K-40K'
});
```

### 3. Property Filter
```typescript
this.analytics.trackPropertyFilter({
  filter_name: 'bedrooms',
  filter_value: '3'
});
```

### 4. Favorite Add/Remove
```typescript
this.analytics.trackFavoriteAdd({
  property_id: '12345',
  property_type: 'apartment'
});

this.analytics.trackFavoriteRemove({
  property_id: '12345',
  property_type: 'apartment'
});
```

### 5. Compare Add/Remove
```typescript
this.analytics.trackCompareAdd({
  property_id: '12345',
  property_type: 'apartment'
});

this.analytics.trackCompareRemove({
  property_id: '12345',
  property_type: 'apartment'
});
```

### 6. Enquiry Start
```typescript
this.analytics.trackEnquiryStart({
  property_id: '12345',
  property_type: 'apartment',
  source: 'property_detail_page'
});
```

### 7. Enquiry Submit
```typescript
this.analytics.trackEnquirySubmit({
  property_id: '12345',
  property_type: 'apartment',
  enquiry_type: 'general',
  source: 'property_detail_page'
});
```

### 8. Builder Contact
```typescript
this.analytics.trackBuilderContact({
  builder_id: 'builder_123',
  property_id: '12345',
  contact_method: 'phone'
});
```

### 9. Seller Contact
```typescript
this.analytics.trackSellerContact({
  seller_listing_id: 'seller_456',
  property_id: '12345',
  contact_method: 'whatsapp'
});
```

### 10. WhatsApp Click
```typescript
this.analytics.trackWhatsAppClick({
  property_id: '12345',
  source: 'property_card'
});
```

### 11. Phone Click
```typescript
this.analytics.trackPhoneClick({
  property_id: '12345',
  source: 'property_detail'
});
```

### 12. User Signup
```typescript
this.analytics.trackSignup({
  method: 'email' // or 'google'
});
```

### 13. User Login
```typescript
this.analytics.trackLogin({
  method: 'email' // or 'google'
});
```

### 14. Custom Events
```typescript
this.analytics.trackEvent('custom_event_name', {
  custom_param_1: 'value1',
  custom_param_2: 'value2'
});
```

## Event Parameters

### All Events Include:
- `event` - The event name (e.g., 'property_view', 'favorite_add')
- Custom parameters specific to each event type

### Parameter Guidelines:
- Use internal IDs only (property_id, builder_id, etc.)
- **NEVER** include PII: names, emails, phone numbers, addresses, Aadhaar, PAN
- Use categorical values for filters (e.g., '3BHK' not '3 bedroom apartment')
- Keep parameter values consistent across events

## Privacy & Security

### ✅ Safe to Track:
- Property IDs
- Builder IDs
- Property types
- Localities/areas
- Price ranges
- Bedroom counts
- Filter selections
- Button clicks
- Page views

### ❌ NEVER Track:
- User names
- Email addresses
- Phone numbers
- Passwords
- JWT tokens
- Authentication tokens
- Aadhaar numbers
- PAN numbers
- Full addresses
- Enquiry message content
- Any personally identifiable information

## SPA Page Tracking

The application automatically tracks page views on route changes. This is handled by:

1. `AnalyticsService.trackPageViews()` method
2. Angular Router's `NavigationEnd` event
3. Duplicate prevention mechanism

**Tracked pages include:**
- Home
- Property listings
- Property details
- Search results
- Project/builder pages
- Seller listings
- User dashboard
- Login/registration pages

## Testing

### Local Testing
1. Open Chrome DevTools
2. Go to Console tab
3. Type: `dataLayer`
4. Verify the array contains your events

### GTM Preview Mode
1. Go to [Google Tag Manager](https://tagmanager.google.com/)
2. Open container `GTM-TGZ9ZL9K`
3. Click "Preview"
4. Enter your website URL
5. Verify events fire correctly

### GA4 DebugView
1. Go to [Google Analytics](https://analytics.google.com/)
2. Open property with ID `G-9WEPYXSXVC`
3. Navigate to Configure → DebugView
4. Enable debug mode in your browser:
   ```
   chrome://flags/#enable-experimental-web-platform-features
   ```
5. Verify events appear in real-time

### Test Checklist
- [ ] Application loads without errors
- [ ] GTM script loads (check Network tab)
- [ ] GA4 script loads (check Network tab)
- [ ] `window.dataLayer` exists
- [ ] Page views tracked on navigation
- [ ] Property view events fire
- [ ] Search events fire
- [ ] Favorite add/remove events fire
- [ ] Compare add/remove events fire
- [ ] Enquiry events fire
- [ ] Contact click events fire
- [ ] Auth events fire (signup/login)
- [ ] No PII in any events
- [ ] No console errors related to analytics

## Performance

### Optimizations Implemented:
1. **Async Loading**: Both GTM and GA4 scripts load asynchronously
2. **Non-blocking**: Analytics never blocks application rendering
3. **Error Handling**: All analytics calls wrapped in try-catch
4. **Graceful Degradation**: Application works even if GTM/GA4 fail to load
5. **Duplicate Prevention**: Page views tracked only once per unique URL
6. **Lazy Initialization**: dataLayer initialized only when needed

### Best Practices:
- Keep analytics calls lightweight
- Avoid firing events in tight loops
- Don't track every user interaction
- Use debouncing for frequent events (e.g., scroll tracking)

## GTM Configuration Required

In Google Tag Manager, you need to configure:

### Tags to Create:
1. **GA4 Configuration Tag**
   - Tag Type: Google Analytics: GA4 Configuration
   - Measurement ID: `G-9WEPYXSXVC`
   - Trigger: All Pages

2. **GA4 Event Tags** (for each custom event)
   - Tag Type: Google Analytics: GA4 Event
   - Configuration Tag: Select GA4 Configuration tag
   - Event Name: Use dataLayer variable
   - Event Parameters: Map dataLayer variables

### Variables to Create:
- `dlv - event` (Data Layer Variable: event)
- `dlv - property_id` (Data Layer Variable: property_id)
- `dlv - property_type` (Data Layer Variable: property_type)
- And other parameters as needed

### Triggers to Create:
- Custom Event triggers for each event type:
  - `property_view`
  - `property_search`
  - `favorite_add`
  - `favorite_remove`
  - `compare_add`
  - `compare_remove`
  - `enquiry_start`
  - `enquiry_submit`
  - `builder_contact`
  - `seller_contact`
  - `whatsapp_click`
  - `phone_click`
  - `signup`
  - `login`

## GA4 Configuration Required

In Google Analytics 4:

1. **Custom Events**: Events will appear automatically in GA4 once GTM is configured
2. **Custom Dimensions** (recommended):
   - `property_type`
   - `listing_type`
   - `locality`
   - `bedrooms`
   - `price_range`
3. **Custom Metrics**: None required initially
4. **Conversions**: Mark these events as conversions:
   - `enquiry_submit`
   - `signup`
   - `builder_contact`
   - `seller_contact`

## Troubleshooting

### GTM Not Loading
- Check network requests for `googletagmanager.com`
- Verify GTM ID in environment files
- Check browser console for errors

### Events Not Firing
- Verify `window.dataLayer` exists
- Check dataLayer array in console: `console.log(window.dataLayer)`
- Ensure AnalyticsService is properly injected
- Use GTM Preview mode to debug

### Duplicate Page Views
- Check if multiple components are calling `trackPageViews()`
- Verify the duplicate prevention mechanism is working
- Check Router events aren't being subscribed multiple times

### Application Breaks
- Analytics should never break the app
- Check console for errors
- Verify try-catch blocks are in place
- Test with GTM/GA4 blocked (using ad blocker)

## Build & Deployment

### Build Command:
```bash
npm run build
```

### Production Deployment:
The production build automatically uses `environment.prod.ts` which contains:
- `gtmId: 'GTM-TGZ9ZL9K'`
- `ga4MeasurementId: 'G-9WEPYXSXVC'`

### Verify After Deployment:
1. Visit production site
2. Open DevTools → Network
3. Verify GTM and GA4 scripts load
4. Check Console for `dataLayer`
5. Navigate between pages
6. Verify events in GA4 DebugView

## Support & Resources

- [Google Tag Manager Help](https://support.google.com/tagmanager)
- [GA4 Help Center](https://support.google.com/analytics)
- [GTM Container: GTM-TGZ9ZL9K](https://tagmanager.google.com/)
- [GA4 Property: G-9WEPYXSXVC](https://analytics.google.com/)

## Contact

For questions or issues with analytics implementation, contact your development team or analytics administrator.
