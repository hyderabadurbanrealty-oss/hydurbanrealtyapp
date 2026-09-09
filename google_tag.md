Implement Google Tag Manager and GA4 analytics in the HydUrbanRealty website.

GOOGLE TAG MANAGER
------------------
The existing Google Tag Manager Container ID is:

GTM-TGZ9ZL9K

Install GTM correctly using the framework's recommended integration method.

Do NOT create a second GTM installation if one already exists.

The equivalent GTM installation is:

<script>
(function(w,d,s,l,i){
  w[l]=w[l]||[];
  w[l].push({'gtm.start': new Date().getTime(),event:'gtm.js'});
  var f=d.getElementsByTagName(s)[0],
  j=d.createElement(s),
  dl=l!='dataLayer'?'&l='+l:'';
  j.async=true;
  j.src='https://www.googletagmanager.com/gtm.js?id='+i+dl;
  f.parentNode.insertBefore(j,f);
})(window,document,'script','dataLayer','GTM-TGZ9ZL9K');
</script>

Also implement the GTM <noscript> iframe fallback where appropriate for the framework.

IMPORTANT:
- Do not hardcode GA4 Measurement IDs throughout the application.
- GTM ID may be stored in an environment variable if the project's configuration supports this.
- Recommended variable:

VITE_GTM_ID=GTM-TGZ9ZL9K

- Do not expose passwords, JWTs, email addresses, phone numbers, names, enquiry text, Aadhaar, PAN, or other PII to GA4.
- Do not duplicate existing analytics implementations.

DATA LAYER
----------
Create a centralized analytics/dataLayer utility.

Example:

window.dataLayer = window.dataLayer || [];

window.dataLayer.push({
  event: "property_view",
  property_id: "12345",
  property_type: "apartment",
  locality: "Raidurg",
  city: "Hyderabad"
});

Create reusable functions such as:

trackEvent()
trackPageView()
trackPropertyView()
trackPropertySearch()
trackFavorite()
trackCompare()
trackEnquiryStart()
trackEnquirySubmit()
trackBuilderContact()
trackSellerContact()
trackWhatsAppClick()
trackPhoneClick()
trackSignup()

EVENTS
------

1. property_view

Parameters:
- property_id
- property_type
- listing_type
- locality
- city
- price_range
- bedrooms

2. property_search

Parameters:
- search_type
- locality
- property_type
- listing_type
- bedrooms
- price_range

3. property_filter

Parameters:
- filter_name
- filter_value

4. favorite_add

Parameters:
- property_id
- property_type

5. favorite_remove

Parameters:
- property_id
- property_type

6. compare_add

Parameters:
- property_id
- property_type

7. compare_remove

Parameters:
- property_id
- property_type

8. enquiry_start

Parameters:
- property_id
- property_type
- source

9. enquiry_submit

Parameters:
- property_id
- property_type
- enquiry_type
- source

10. builder_contact

Parameters:
- builder_id
- property_id
- contact_method

11. seller_contact

Parameters:
- seller_listing_id
- property_id
- contact_method

12. whatsapp_click

Parameters:
- property_id
- source

13. phone_click

Parameters:
- property_id
- source

14. signup

Parameters:
- signup_method

15. login

Parameters:
- login_method


SPA PAGE TRACKING
-----------------
HydUrbanRealty is a web application, so correctly track route changes.

Track page views for:

- Home
- Property listing
- Property details
- Search results
- Project/builder pages
- Seller listings
- Login
- Registration
- Dashboard
- Other important pages

Prevent duplicate page_view events caused by component re-renders.

GOOGLE ANALYTICS 4
------------------
Configure GA4 through Google Tag Manager.

Do not add GA4 directly to every component.

Use:

Application
    ↓
analytics utility
    ↓
dataLayer
    ↓
Google Tag Manager
    ↓
GA4

GTM should be responsible for the GA4 configuration/tag.

PRIVACY
-------
Never send:

- Name
- Email
- Phone
- Password
- JWT
- Authentication token
- Aadhaar
- PAN
- Full address
- Enquiry message
- Other personally identifiable information

Use internal IDs such as property_id and builder_id.

ERROR SAFETY
------------
Analytics must never break the application.

If GTM is unavailable or not configured:

- application must continue working
- analytics calls should safely become no-ops
- no fatal console errors

PERFORMANCE
-----------
- Load GTM asynchronously.
- Do not block application rendering.
- Do not fire duplicate events.
- Keep analytics code centralized.

TESTING
-------
After implementation:

1. Run frontend build.
2. Run lint/type checks.
3. Verify application works with GTM disabled.
4. Verify GTM-TGZ9ZL9K loads when configured.
5. Verify dataLayer events.
6. Verify property_view.
7. Verify property_search.
8. Verify favorite.
9. Verify compare.
10. Verify enquiry_submit.
11. Verify WhatsApp click.
12. Verify phone click.
13. Verify signup/login.
14. Verify SPA page views.
15. Verify no PII is sent.

DOCUMENTATION
-------------
Document:

- GTM Container ID: GTM-TGZ9ZL9K
- Environment variable configuration
- Analytics utility location
- DataLayer implementation
- All supported events
- Event parameters
- GTM configuration required
- GA4 configuration required
- How to test using GTM Preview
- How to verify events using GA4 DebugView

FINAL RESPONSE
--------------
After implementation, report:

1. Files created/modified
2. GTM installation location
3. Events implemented
4. GTM/GA4 configuration still required
5. Build/test result
6. Any issues or assumptions



<!-- Google tag (gtag.js) -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-9WEPYXSXVC"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());

  gtag('config', 'G-9WEPYXSXVC');
</script>

