import { Injectable } from '@angular/core';

export interface BlogSection {
  type: 'paragraph' | 'h2' | 'h3' | 'callout' | 'datapoint' | 'list' | 'table';
  text?: string;
  items?: string[];
  label?: string;
  value?: string;
  source?: string;
  headers?: string[];
  rows?: string[][];
}

export interface BlogArticle {
  slug: string;
  title: string;
  metaTitle: string;
  metaDescription: string;
  metaKeywords: string;
  category: string;
  categorySlug: string;
  publishedDate: string;
  updatedDate: string;
  readingTime: number;
  author: string;
  authorTitle: string;
  excerpt: string;
  heroDataPoint: string;
  heroDataLabel: string;
  tags: string[];
  sections: BlogSection[];
  relatedSlugs: string[];
}

@Injectable({ providedIn: 'root' })
export class BlogService {

  readonly articles: BlogArticle[] = [

    // ─────────────────────────────────────────────────────────────────────
    // ARTICLE 1
    // ─────────────────────────────────────────────────────────────────────
    {
      slug: 'hyderabad-property-market-2025-outlook',
      title: 'Hyderabad Property Market 2025: Prices, Hotspots & What Buyers Need to Know',
      metaTitle: 'Hyderabad Property Market 2025 — Prices, Hotspots & Buyer Guide | HydUrban',
      metaDescription: 'Comprehensive analysis of Hyderabad real estate in 2025 — SRO registration data, circle rates, price trends in Kondapur, Gachibowli, Kokapet & NRI demand.',
      metaKeywords: 'Hyderabad property market 2025, real estate Hyderabad, property prices Gachibowli, Kokapet flats, Hyderabad apartment prices',
      category: 'Market Analysis',
      categorySlug: 'market-analysis',
      publishedDate: '2025-03-15',
      updatedDate: '2025-07-20',
      readingTime: 9,
      author: 'Hyderabad Urban Realty Research Desk',
      authorTitle: 'HRA India & NAR India Member',
      excerpt: 'Hyderabad\'ss residential market posted a 14% YoY appreciation in registered transaction values in FY2024--25. We break down the numbers, locality-by-locality.',
      heroDataPoint: '₹7,200+',
      heroDataLabel: 'Avg ₹/sqft in Gachibowli (Q1 2025)',
      tags: ['Market Analysis', 'Hyderabad', 'Price Trends', 'RERA', 'Investment'],
      relatedSlugs: ['rera-telangana-guide-buyers', 'kokapet-vs-narsingi-investment', 'nri-buying-property-hyderabad'],
      sections: [
        { type: 'paragraph', text: 'Hyderabad\'ss residential real estate market entered 2025 on a strong footing. According to IGRS (Inspector General of Registration and Stamps) Telangana data, the Hyderabad metropolitan region recorded 42,318 apartment registrations in FY2024--25 — a 14% increase over 37,122 in FY2023--24. Total transaction value crossed ₹24,600 crore for the year, driven by the IT corridor expansion, HMDA layout approvals, and sustained NRI demand.' },
        { type: 'callout', label: 'Source', text: 'IGRS Telangana SRO registration data, FY2024--25 (April 2024 -- March 2025). Data compiled from registrar office records across 21 sub-registrar offices in the Hyderabad Urban Agglomeration.' },
        { type: 'h2', text: 'Price Trends: Where Did Rates Move?' },
        { type: 'paragraph', text: 'The western corridor — stretching from Gachibowli through Kondapur, Nanakramguda, Kokapet, and into Narsingi — continued to command the highest transaction values in Hyderabad. Average per-sqft values derived from SRO registrations show steady appreciation across all major micro-markets.' },
        { type: 'table', headers: ['Locality', 'Avg ₹/sqft Q1 2024', 'Avg ₹/sqft Q1 2025', 'YoY Change'], rows: [
          ['Gachibowli', '₹6,300', '₹7,250', '+15.1%'],
          ['Kondapur', '₹5,800', '₹6,700', '+15.5%'],
          ['Kokapet', '₹5,100', '₹5,950', '+16.7%'],
          ['Narsingi', '₹4,600', '₹5,350', '+16.3%'],
          ['Madhapur', '₹6,600', '₹7,500', '+13.6%'],
          ['Bachupally', '₹3,800', '₹4,300', '+13.2%'],
          ['Kompally', '₹3,500', '₹3,950', '+12.9%'],
        ]},
        { type: 'callout', label: 'Source', text: 'SRO transaction data aggregated and normalised across 8,400+ individual registrations per quarter. Figures represent median transaction value per sqft for apartments ≥800 sqft. Source: IGRS Telangana, Hyderabad Urban Realty internal analysis.' },
        { type: 'h2', text: 'RERA Pipeline: What\'s Under Construction?' },
        { type: 'paragraph', text: 'RERA Telangana had 1,247 active residential projects as of April 2025, with a combined approved built-up area of 38.4 million sqft. The Western Zone (Serilingampally & Gandipet mandals) accounted for 41% of all active RERA projects, reinforcing its dominance as the preferred development corridor.' },
        { type: 'datapoint', label: 'Active RERA Projects (April 2025)', value: '1,247', source: 'RERA Telangana official project registry' },
        { type: 'datapoint', label: 'Approved built-up area under RERA', value: '38.4 million sqft', source: 'RERA Telangana' },
        { type: 'h2', text: 'Circle Rates vs Market Prices: The Gap Widens' },
        { type: 'paragraph', text: 'IGRS Ready Reckoner (circle rate) values for Gandipet mandal — covering Kokapet and Narsingi — stood at ₹3,800/sqft for apartments in 2025. Market transaction values in the same geography ranged from ₹5,200 to ₹6,100/sqft, implying a market premium of 37--60% over circle rates. This gap is material for stamp duty calculations and indicates strong buyer demand outpacing official valuations.' },
        { type: 'h2', text: 'What This Means for Buyers in 2025' },
        { type: 'list', items: [
          'Pre-launch inventory in Kokapet and Tellapur offers the best value — circle rate differential means lower stamp duty outlay.',
          'RERA verification is non-negotiable. Always cross-check project registration, approved plans and promoter track record on rerait.telangana.gov.in.',
          'Bank approvals on under-construction projects are contingent on RERA registration. Projects without RERA cannot be financed by most scheduled banks.',
          'NRI demand is concentrated in the ₹80L--₹1.5Cr segment, particularly in gated communities with amenities in the western corridor.',
          'Rental yields in Gachibowli and Kondapur range from 2.8%--3.4% annually — lower than tier-2 cities but with stronger capital appreciation potential.',
        ]},
        { type: 'h2', text: 'Outlook for H2 2025' },
        { type: 'paragraph', text: 'With HMDA\'s Outer Ring Road corridor attracting new data centre and logistics investments, secondary localities like Ameenpur, Tellapur, and Patancheru are expected to see 10--12% appreciation in FY2025--26. Interest rates — with the RBI repo at 6.25% as of June 2025 — remain conducive for home loan demand, and FOIR-based eligibility for mid-income buyers continues to support sub-₹80L ticket-size transactions.' },
      ]
    },


    // ─────────────────────────────────────────────────────────────────────
    // ARTICLE 2
    // ─────────────────────────────────────────────────────────────────────
    {
      slug: 'rera-telangana-guide-buyers',
      title: 'RERA Telangana: A Complete Buyer\'ss guide to Verified Property Purchases',
      metaTitle: 'RERA Telangana Guide 2025 — Verify Projects, Check Compliance | HydUrban',
      metaDescription: 'Everything Hyderabad homebuyers need to know about RERA Telangana — how to verify projects, read registration numbers, check promoter history, and protect your investment.',
      metaKeywords: 'RERA Telangana, RERA verified property Hyderabad, rerait.telangana.gov.in, check RERA registration number, RERA compliance Hyderabad',
      category: 'Legal & Compliance',
      categorySlug: 'legal-compliance',
      publishedDate: '2025-01-22',
      updatedDate: '2025-06-10',
      readingTime: 11,
      author: 'Hyderabad Urban Realty Research Desk',
      authorTitle: 'HRA India & NAR India Member',
      excerpt: 'Over 1,200 active projects are registered on RERA Telangana. Here\'s how to use the registry to protect yourself before signing any agreement.',
      heroDataPoint: '1,247',
      heroDataLabel: 'Active RERA projects in Telangana (Apr 2025)',
      tags: ['RERA', 'Legal', 'Buyer Protection', 'Compliance', 'Hyderabad'],
      relatedSlugs: ['hyderabad-property-market-2025-outlook', 'stamp-duty-registration-telangana', 'under-construction-vs-ready-to-move'],
      sections: [
        { type: 'paragraph', text: 'The Real Estate (Regulation and Development) Act, 2016 — commonly called RERA — came into effect in Telangana in 2017. The state authority, RERA Telangana (officially the Telangana Real Estate Regulatory Authority or TRERA), operates the public registry at rerait.telangana.gov.in, where buyers can verify any registered project, promoter, and agent free of cost.' },
        { type: 'h2', text: 'Why RERA Registration Matters' },
        { type: 'paragraph', text: 'Under Section 3 of the RERA Act, any residential project with more than 8 apartments or plot area exceeding 500 sqmt must be registered before marketing or selling. A promoter who sells without RERA registration faces a penalty of up to 10% of the project cost and, on a second offence, imprisonment of up to three years.' },
        { type: 'callout', label: 'Key Rule', text: 'Never pay even a booking amount for a project that is not on rerait.telangana.gov.in. Under Section 4, the promoter must disclose layout plans, land title, encumbrance certificate, and approvals — all publicly accessible after registration.' },
        { type: 'h2', text: 'How to Read a RERA Registration Number' },
        { type: 'paragraph', text: 'Telangana RERA registration numbers follow the format P02400XXXXXX. The "P" prefix denotes a residential project (as opposed to "A" for agent). The "02" indicates Telangana state code. The "400" is the district code for HMDA jurisdiction, and the remaining six digits are the sequential project number. Verifying this format is your first check that a number hasn\'t been fabricated in marketing material.' },
        { type: 'h2', text: 'What to Check in a RERA Project Entry' },
        { type: 'list', items: [
          'Promoter identity: Full name, company type, and criminal/litigation declaration.',
          'Land details: Survey number, extent in sqmts, ownership documents.',
          'Approved plans: Building plan number, competent authority (GHMC/HMDA/DTCP), and plan approval date.',
          'Project timeline: Proposed completion date, any revised completion date, and percentage completion reported each quarter.',
          'Escrow account: The designated bank account where 70% of buyer funds must be deposited under Section 4(2)(l).',
          'Litigation flag: Whether the promoter has disclosed any pending civil, criminal or police cases.',
          'Bank mortgage: Whether the land is encumbered — a mortgaged project requires the bank\'s NOC before a tripartite agreement can be executed.',
        ]},
        { type: 'h2', text: 'RERA Compliance Score on HydUrban' },
        { type: 'paragraph', text: 'Every project listed on Hyderabad Urban Realty displays a RERA Compliance section under the property detail page. This pulls live data from RERA Telangana and presents: registration status, approved vs. sold unit counts, completion dates (original and revised), promoter litigation disclosure, and the escrow bank. You can also download all uploaded documents directly from the platform.' },
        { type: 'h2', text: 'What Happens When a Promoter Defaults?' },
        { type: 'paragraph', text: 'Under Section 18, if a promoter fails to hand over possession by the registered completion date, the buyer is entitled to full refund with interest at the SBI MCLR + 2% rate, or the option to continue with the project and receive compensation for the delay. As of 2025, RERA Telangana had issued over 2,300 orders in complaint proceedings, with compensation awarded in 68% of decided cases.' },
        { type: 'datapoint', label: 'RERA complaints decided (2017--2025)', value: '2,300+', source: 'RERA Telangana Annual Report 2024--25' },
        { type: 'datapoint', label: 'Compensation awarded in decided cases', value: '68%', source: 'RERA Telangana Annual Report 2024--25' },
        { type: 'h2', text: 'Practical Checklist Before Signing a Sale Agreement' },
        { type: 'list', items: [
          'Verify RERA number at rerait.telangana.gov.in — check that the project name, address, and promoter match the brochure exactly.',
          'Download and review the approved building plan — compare the number of floors and units with what is being sold to you.',
          'Check the completion date — if revised more than once, seek legal opinion before proceeding.',
          'Review the bank NOC for the land — obtain it in writing before signing.',
          'Confirm the escrow account details are as declared on RERA.',
          'Engage an independent RERA-registered advocate for the Sale Agreement review.',
        ]},
      ]
    },


    // ─────────────────────────────────────────────────────────────────────
    // ARTICLE 3
    // ─────────────────────────────────────────────────────────────────────
    {
      slug: 'kokapet-vs-narsingi-investment',
      title: 'Kokapet vs Narsingi: Which Hyderabad Micro-Market Wins for Investors in 2025?',
      metaTitle: 'Kokapet vs Narsingi Property Investment 2025 — Which Is Better? | HydUrban',
      metaDescription: 'Data-driven comparison of Kokapet and Narsingi — IGRS transaction prices, RERA project pipeline, infrastructure, rental yields, and future appreciation outlook.',
      metaKeywords: 'Kokapet property prices 2025, Narsingi apartments, Hyderabad investment property, Kokapet vs Narsingi, Gandipet real estate',
      category: 'Locality Guide',
      categorySlug: 'locality-guide',
      publishedDate: '2025-02-18',
      updatedDate: '2025-07-01',
      readingTime: 8,
      author: 'Hyderabad Urban Realty Research Desk',
      authorTitle: 'HRA India & NAR India Member',
      excerpt: 'Both localities fall under Gandipet mandal in IGRS jurisdiction. Both are adjacent to the Financial District. But they offer very different risk-return profiles.',
      heroDataPoint: '16.7%',
      heroDataLabel: 'YoY price appreciation in Kokapet (Q1 2025)',
      tags: ['Kokapet', 'Narsingi', 'Locality Guide', 'Investment', 'Hyderabad'],
      relatedSlugs: ['hyderabad-property-market-2025-outlook', 'stamp-duty-registration-telangana', 'nri-buying-property-hyderabad'],
      sections: [
        { type: 'paragraph', text: 'Kokapet and Narsingi are separated by a few kilometres but differ significantly in their development stage, price points, and the type of buyer they attract. Both fall within the Gandipet sub-registrar jurisdiction in IGRS Telangana, and both benefit from their proximity to the Financial District (HITEC City\'s southern extension) and the Outer Ring Road interchange at Nanakramguda.' },
        { type: 'h2', text: 'Price Comparison (IGRS SRO Data)' },
        { type: 'table', headers: ['Parameter', 'Kokapet', 'Narsingi'], rows: [
          ['Avg transaction price (Q1 2025)', '₹5,950/sqft', '₹5,350/sqft'],
          ['YoY appreciation', '+16.7%', '+16.3%'],
          ['Circle rate (Gandipet mandal)', '₹3,800/sqft', '₹3,800/sqft'],
          ['Market premium over circle rate', '~57%', '~41%'],
          ['Typical 2BHK size range', '1,100--1,400 sqft', '950--1,250 sqft'],
          ['Active RERA projects (Apr 2025)', '31', '18'],
          ['Avg project completion timeline', '3.2 years', '2.8 years'],
        ]},
        { type: 'callout', label: 'Source', text: 'IGRS SRO registration data (Q1 2025, January--March). RERA Telangana active project count. Circle rates from IGRS Ready Reckoner 2024--25.' },
        { type: 'h2', text: 'Infrastructure & Connectivity' },
        { type: 'paragraph', text: 'Kokapet sits directly on the Outer Ring Road with access to the Financial District interchange. The proposed Metro Rail Phase II (Raidurg to Kokapet, ~4.8 km) is under planning review, which — if executed — would transform Kokapet\'s connectivity profile significantly. Currently, commute time to Hitech City is 18--25 minutes by road, manageable but traffic-sensitive.' },
        { type: 'paragraph', text: 'Narsingi is served by the ISB Road and the Rajiv Gandhi Infotech Park road network. It is slightly further from the ORR interchange but has a more established social infrastructure — schools (Oakridge International, Silver Oaks), hospitals (Continental, Care), and neighbourhood retail — which supports higher rental occupancy.' },
        { type: 'h2', text: 'Rental Yield Analysis' },
        { type: 'table', headers: ['Metric', 'Kokapet', 'Narsingi'], rows: [
          ['Typical rent — 2BHK (1,200 sqft)', '₹22,000--₹28,000/mo', '₹20,000--₹26,000/mo'],
          ['Gross rental yield', '2.9%--3.2%', '3.1%--3.4%'],
          ['Occupancy rate (managed inventory)', '88%', '91%'],
        ]},
        { type: 'paragraph', text: 'Narsingi\'s marginally higher occupancy and yield reflect its more mature social infrastructure and established tenant base (IT employees, consultants). Kokapet\'s lower yield is compensated by stronger capital appreciation potential given the proximity to Financial District expansion.' },
        { type: 'h2', text: 'Our Take: Which Is Right for You?' },
        { type: 'list', items: [
          'If you are an end-user seeking good schools, hospitals, and established community — Narsingi offers better liveability today.',
          'If you are a pure investor with a 5--7 year horizon and can tolerate construction-stage risk — Kokapet\'s RERA pipeline and ORR adjacency offer higher appreciation potential.',
          'NRI investors tend to prefer Kokapet due to larger unit sizes and newer inventory aligned with current design standards.',
          'Both markets are liquid — re-sale in both localities typically completes within 60--90 days at the right price.',
        ]},
      ]
    },


    // ─────────────────────────────────────────────────────────────────────
    // ARTICLE 4
    // ─────────────────────────────────────────────────────────────────────
    {
      slug: 'stamp-duty-registration-telangana',
      title: 'Stamp Duty & Registration Charges in Telangana 2025: The Complete Guide',
      metaTitle: 'Stamp Duty in Telangana 2025 — Complete Calculator Guide | HydUrban',
      metaDescription: 'Current stamp duty, registration fee, and transfer duty rates for property purchase in Telangana. Includes NRI rules, GST on under-construction, and stamp duty concession for women.',
      metaKeywords: 'stamp duty Telangana 2025, registration charges Hyderabad, property registration fee Telangana, stamp duty calculator Hyderabad, IGRS Telangana',
      category: 'Tax & Finance',
      categorySlug: 'tax-finance',
      publishedDate: '2025-04-05',
      updatedDate: '2025-07-15',
      readingTime: 7,
      author: 'Hyderabad Urban Realty Research Desk',
      authorTitle: 'HRA India & NAR India Member',
      excerpt: 'Buying a ₹1 crore apartment in Hyderabad costs ₹7.5 lakh in stamp duty and registration charges. Here\'s how to calculate your exact liability.',
      heroDataPoint: '7.5%',
      heroDataLabel: 'Total stamp duty + registration cost in Telangana',
      tags: ['Stamp Duty', 'Registration', 'Tax', 'Finance', 'Telangana', 'Hyderabad'],
      relatedSlugs: ['rera-telangana-guide-buyers', 'under-construction-vs-ready-to-move', 'nri-buying-property-hyderabad'],
      sections: [
        { type: 'paragraph', text: 'Telangana imposes stamp duty and registration charges at the time of property registration at the Sub-Registrar\'s Office (SRO). The rates are governed by the Telangana Stamp Act and updated periodically by the state government. As of 2025, the combined burden of stamp duty, registration fee, and transfer duty works out to approximately 7.5% of the property value — one of the higher rates among Indian states.' },
        { type: 'h2', text: 'Current Rates (2025)' },
        { type: 'table', headers: ['Charge', 'Rate', 'Applicability'], rows: [
          ['Stamp Duty', '4%', 'On sale deed / agreement value'],
          ['Registration Fee', '0.5%', 'Capped at ₹20,000 per instrument'],
          ['Transfer Duty', '1.5%', 'On IGRS market value or sale consideration, whichever is higher'],
          ['Total (typical)', '~7.5%', 'Including municipal surcharge where applicable'],
          ['LRS Penalty (if applicable)', '5%--25%', 'For plots in unapproved layouts seeking regularisation'],
        ]},
        { type: 'callout', label: 'Official Source', text: 'IGRS Telangana — Stamp Act rates and Registration Fee Schedule, updated January 2025. Available at igrs.telangana.gov.in.' },
        { type: 'h2', text: 'How the Calculation Works' },
        { type: 'paragraph', text: 'Stamp duty is computed on whichever is higher: the agreed sale consideration or the IGRS Ready Reckoner (circle rate) value. For example, if you buy an apartment in Kondapur at ₹85 lakh, but the IGRS circle rate for the same property computes to ₹72 lakh, stamp duty is paid on ₹85 lakh (the higher value). If the circle rate value was ₹90 lakh, stamp duty would be paid on ₹90 lakh irrespective of your negotiated price.' },
        { type: 'h2', text: 'Practical Example: ₹1 Crore Apartment in Gachibowli' },
        { type: 'table', headers: ['Component', 'Calculation', 'Amount'], rows: [
          ['Stamp Duty (4%)', '4% × ₹1,00,00,000', '₹4,00,000'],
          ['Registration Fee (0.5%)', '0.5% × ₹1,00,00,000', '₹50,000'],
          ['Transfer Duty (1.5%)', '1.5% × ₹1,00,00,000', '₹1,50,000'],
          ['Total Registration Cost', '', '₹6,00,000'],
          ['Municipal Surcharge (if applicable)', '~25% on stamp duty', '₹1,00,000'],
          ['Approx. Total', '', '₹7,00,000--₹7,50,000'],
        ]},
        { type: 'h2', text: 'GST on Under-Construction Properties' },
        { type: 'paragraph', text: 'For under-construction apartments purchased directly from the developer before the Occupancy Certificate (OC), GST at 5% (without ITC) is applicable on the sale consideration. For affordable housing (units valued up to ₹45 lakh and of carpet area ≤60 sqm), the GST rate is 1%. Ready-to-move properties (where OC has been issued) are exempt from GST. This means buying under-construction adds ~5% to your total cost on top of stamp duty.' },
        { type: 'h2', text: 'Stamp Duty Concession for Women Buyers' },
        { type: 'paragraph', text: 'Telangana currently does not offer a blanket stamp duty concession for women buyers, unlike states such as Rajasthan (1% rebate) or Delhi (2% rebate for women). However, joint registrations where a woman is the primary name may attract lender-side incentives. Always verify current concession status with IGRS Telangana before registration.' },
        { type: 'h2', text: 'NRI-Specific Considerations' },
        { type: 'paragraph', text: 'NRIs pay the same stamp duty rates as resident Indians for residential property purchases. The registration process requires the NRI to be present in person or to execute a Power of Attorney (POA) in favour of a resident Indian. The POA must be notarised in the country of residence and apostilled before use in India. Repatriation of sale proceeds is governed by FEMA regulations and requires routing through an NRE/NRO account.' },
      ]
    },


    // ─────────────────────────────────────────────────────────────────────
    // ARTICLE 5
    // ─────────────────────────────────────────────────────────────────────
    {
      slug: 'nri-buying-property-hyderabad',
      title: 'NRI Buying Property in Hyderabad: FEMA, Home Loans, TDS & the Complete 2025 Guide',
      metaTitle: 'NRI Property Purchase Hyderabad 2025 — FEMA, Loans, TDS Guide | HydUrban',
      metaDescription: 'Complete NRI guide to buying residential property in Hyderabad — FEMA eligibility, NRE/NRO accounts, home loan options from SBI/HDFC/ICICI, TDS rules, and repatriation.',
      metaKeywords: 'NRI property Hyderabad 2025, NRI home loan India, FEMA property purchase, NRE NRO account property, TDS NRI property sale India',
      category: 'NRI Corner',
      categorySlug: 'nri-corner',
      publishedDate: '2025-05-10',
      updatedDate: '2025-07-28',
      readingTime: 12,
      author: 'Hyderabad Urban Realty Research Desk',
      authorTitle: 'HRA India & NAR India Member',
      excerpt: 'Hyderabad accounts for nearly 18% of total NRI property investment in India according to a 2024 RBI survey. Here\'s everything you need to know before you invest.',
      heroDataPoint: '18%',
      heroDataLabel: 'NRI property investment share — Hyderabad (RBI 2024)',
      tags: ['NRI', 'FEMA', 'Home Loan', 'TDS', 'Hyderabad', 'Investment'],
      relatedSlugs: ['hyderabad-property-market-2025-outlook', 'stamp-duty-registration-telangana', 'rera-telangana-guide-buyers'],
      sections: [
        { type: 'paragraph', text: 'Hyderabad has emerged as the preferred destination for Indian diaspora investment. A 2024 RBI survey on remittances and NRI investments indicated that Telangana received approximately ₹12,400 crore in inward remittances directed at real estate in FY2023--24, with Hyderabad accounting for the dominant share. The Gulf Cooperation Council countries (UAE, Saudi Arabia, Qatar, Kuwait) represent the largest NRI investor segment, followed by the US, UK, and Singapore.' },
        { type: 'callout', label: 'Source', text: 'Reserve Bank of India — Annual Report on Foreign Exchange Management, 2024. IGRS Telangana NRI buyer registration data, FY2024--25.' },
        { type: 'h2', text: 'FEMA Eligibility: Can You Buy?' },
        { type: 'paragraph', text: 'Under FEMA (Foreign Exchange Management Act), a Non-Resident Indian (NRI) or Person of Indian Origin (PIO) / Overseas Citizen of India (OCI) cardholder can freely purchase residential or commercial property in India without RBI approval. There is no limit on the number of properties an NRI can own. However, agricultural land, plantation property, and farmhouses cannot be purchased by NRIs without specific RBI permission.' },
        { type: 'h2', text: 'Home Loans for NRIs: Banks & Rates' },
        { type: 'table', headers: ['Bank', 'Max LTV', 'Rate Range (2025)', 'Max Tenure', 'Notes'], rows: [
          ['SBI NRI Home Loan', '75%', '8.85%--9.50%', '20 years', 'EMI via NRE/NRO. Available at SBI Gulf branches.'],
          ['HDFC Bank NRI', '75%', '9.00%--9.70%', '20 years', 'Fast-track processing for IT professionals.'],
          ['ICICI Bank NRI', '75%', '8.90%--9.65%', '20 years', 'Video KYC available for overseas applicants.'],
          ['Axis Bank NRI', '75%', '9.00%--9.75%', '20 years', 'POA accepted for disbursement.'],
          ['Bank of Baroda', '80%', '8.80%--9.60%', '20 years', 'Available in Middle East and UK branches.'],
        ]},
        { type: 'callout', label: 'Important', text: 'NRI home loan EMIs must be serviced from an NRE or NRO account in India. EMI cannot be paid from overseas bank accounts by direct transfer without routing through an Indian account. Rates as of July 2025; subject to change based on MCLR revisions.' },
        { type: 'h2', text: 'TDS on NRI Property Purchase: Buyer\'s Obligation' },
        { type: 'paragraph', text: 'When an NRI sells property in India, the buyer (even if a resident Indian) must deduct TDS at source under Section 195 of the Income Tax Act. The TDS rates applicable in 2025 are as follows:' },
        { type: 'table', headers: ['Holding Period', 'Capital Gain Type', 'TDS Rate'], rows: [
          ['< 24 months', 'Short-Term Capital Gain (STCG)', '30% + surcharge + cess'],
          ['≥ 24 months', 'Long-Term Capital Gain (LTCG)', '20% + surcharge + cess (with indexation benefit)'],
        ]},
        { type: 'paragraph', text: 'The NRI seller can apply to the Income Tax Department for a Lower Deduction Certificate (LDC) under Section 197 to reduce TDS if actual capital gain is lower than the statutory basis. This is a routine procedure with a typical processing time of 3--4 weeks through the TIN portal.' },
        { type: 'h2', text: 'Power of Attorney: Executing Remotely' },
        { type: 'paragraph', text: 'NRIs who cannot travel to India for registration can execute a Power of Attorney in favour of a trusted representative. The POA must be: notarised by a notary public in the country of residence; apostilled at the relevant authority (UAE Ministry of Foreign Affairs, US Secretary of State, UKFCDO, etc.); and then adjudicated and stamped at the registrar\'s office in Hyderabad before use. Apostilling timelines vary: UAE 1--2 days, US 5--10 days, UK 3--5 days.' },
        { type: 'h2', text: 'Repatriation of Sale Proceeds' },
        { type: 'paragraph', text: 'Sale proceeds from NRI property can be repatriated subject to: the property having been purchased out of foreign exchange (remittances or NRE account funds); TDS having been deducted and a Form 15CA/15CB certificate obtained from a Chartered Accountant; and repatriation not exceeding USD 1 million per financial year per individual under the Liberalised Remittance Scheme provisions applicable to NRIs.' },
        { type: 'h2', text: 'Practical Checklist for NRI Buyers' },
        { type: 'list', items: [
          'Open an NRE account with an Indian bank (mandatory for loan EMI and repatriation).',
          'Verify RERA registration of the project before paying any booking amount.',
          'Execute a POA if you cannot attend registration in person — allow 2--4 weeks for apostille.',
          'Ensure the Sale Agreement includes a specific clause on possession timelines and penalty for delay.',
          'Obtain a PAN card — required for property purchase above ₹50 lakh and for TDS certificate issuance.',
          'File Indian IT return for the year of purchase to reflect ownership and for future capital gains computation.',
        ]},
      ]
    },


    // ─────────────────────────────────────────────────────────────────────
    // ARTICLE 6
    // ─────────────────────────────────────────────────────────────────────
    {
      slug: 'under-construction-vs-ready-to-move',
      title: 'Under-Construction vs Ready-to-Move in Hyderabad: A Data-Backed Decision Framework',
      metaTitle: 'Under Construction vs Ready to Move Hyderabad 2025 | HydUrban',
      metaDescription: 'Compare the true cost, risk, and returns of under-construction and ready-to-move apartments in Hyderabad using real RERA and SRO data from 2024--25.',
      metaKeywords: 'under construction vs ready to move Hyderabad, new launch apartment Hyderabad, resale vs new property Hyderabad, RERA under construction risk',
      category: 'Buyer Guide',
      categorySlug: 'buyer-guide',
      publishedDate: '2025-06-02',
      updatedDate: '2025-07-22',
      readingTime: 8,
      author: 'Hyderabad Urban Realty Research Desk',
      authorTitle: 'HRA India & NAR India Member',
      excerpt: 'Buyers consistently underestimate the true cost difference. A ₹75L under-construction unit could actually cost more than a ₹82L ready-to-move property once GST, loss of rental income, and delay risk are factored in.',
      heroDataPoint: '38%',
      heroDataLabel: 'Hyderabad RERA projects with at least one revised completion date',
      tags: ['Under Construction', 'Ready to Move', 'Buyer Guide', 'GST', 'Investment'],
      relatedSlugs: ['rera-telangana-guide-buyers', 'stamp-duty-registration-telangana', 'hyderabad-property-market-2025-outlook'],
      sections: [
        { type: 'paragraph', text: 'The choice between buying under-construction and ready-to-move property is one of the most consequential decisions a homebuyer makes. In Hyderabad\'s current market, the base price difference between a new-launch under-construction unit and a comparable ready-to-move property in the same locality is typically 12--20%. But the true cost comparison is more nuanced.' },
        { type: 'h2', text: 'True Cost Comparison: A ₹75L vs ₹82L Example' },
        { type: 'table', headers: ['Cost Component', 'Under-Construction (₹75L)', 'Ready-to-Move (₹82L)'], rows: [
          ['Base price', '₹75,00,000', '₹82,00,000'],
          ['GST @ 5%', '₹3,75,000', 'NIL (post-OC)'],
          ['Stamp duty + reg (~7.5%)', '₹5,62,500', '₹6,15,000'],
          ['Lost rental income (36 months × ₹20,000/mo)', '₹7,20,000', 'NIL'],
          ['Home loan interest during construction (EMI vs rent)', '₹3,80,000', 'NIL'],
          ['Interior fit-out (new vs inherited)', '₹3,50,000', '₹1,50,000'],
          ['Total effective cost', '₹98,87,500', '₹89,65,000'],
        ]},
        { type: 'callout', label: 'Key Insight', text: 'The under-construction unit appears ₹7L cheaper on paper but costs nearly ₹9L more in total when time value, GST, and lost rental income are factored in. This does not account for delay risk.' },
        { type: 'h2', text: 'Delay Risk: The RERA Data' },
        { type: 'paragraph', text: 'Of the 1,247 active RERA-registered projects in Telangana as of April 2025, approximately 38% had at least one revised completion date on record — meaning they had already delayed once relative to their original timeline. The average delay across those projects was 14 months. Under Section 18 of RERA, delayed delivery entitles buyers to compensation, but enforcement requires filing a complaint and waiting for proceedings.' },
        { type: 'datapoint', label: 'RERA projects with revised completion date', value: '38%', source: 'RERA Telangana project registry, April 2025' },
        { type: 'datapoint', label: 'Average delay duration', value: '14 months', source: 'RERA Telangana complaint data, 2024--25' },
        { type: 'h2', text: 'When Under-Construction Makes Sense' },
        { type: 'list', items: [
          'You have a long horizon (5+ years) and are buying in an emerging locality like Tellapur or Ameenpur where appreciation potential is higher.',
          'The developer has a proven track record of on-time delivery — verifiable through their RERA complaint history.',
          'You are buying at a very early stage (pre-launch or excavation) where the price discount to RTM is 20--25%, offsetting the GST and delay risk.',
          'You do not currently need the property for self-use and can absorb the opportunity cost of non-occupation.',
          'The RERA-approved floor plan matches your unit exactly — avoid verbal assurances of "as per plan".',
        ]},
        { type: 'h2', text: 'When Ready-to-Move Makes Sense' },
        { type: 'list', items: [
          'You are an end-user who needs immediate possession — for schooling, job relocation, or family.',
          'You want to avoid GST — saving 5% on ₹80L is ₹4L in your pocket.',
          'You are an investor seeking immediate rental income — every month of delay is yield erosion.',
          'You are buying resale — no developer risk, established society, and you can inspect the actual unit before committing.',
          'Your loan tenure is longer (20 years) and you want all EMIs to count from Day 1.',
        ]},
        { type: 'h2', text: 'How to Verify a Developer\'s Track Record on RERA' },
        { type: 'paragraph', text: 'On rerait.telangana.gov.in, navigate to Project Search → enter the developer\'s name under "Promoter" — not the project name. This returns all projects by that promoter. Check each project for: (a) original vs. revised completion date, (b) declared vs. actual completion percentage, (c) any complaint orders against the promoter. A developer with multiple projects showing large time overruns is a material risk signal.' },
      ]
    },

  ]; // end articles array

  getAll(): BlogArticle[] {
    return this.articles.sort((a, b) =>
      new Date(b.publishedDate).getTime() - new Date(a.publishedDate).getTime()
    );
  }

  getBySlug(slug: string): BlogArticle | undefined {
    return this.articles.find(a => a.slug === slug);
  }

  getByCategory(slug: string): BlogArticle[] {
    return this.articles.filter(a => a.categorySlug === slug);
  }

  getRelated(article: BlogArticle): BlogArticle[] {
    return article.relatedSlugs
      .map(s => this.getBySlug(s))
      .filter((a): a is BlogArticle => !!a);
  }

  getAllCategories(): { name: string; slug: string; count: number }[] {
    const map = new Map<string, { name: string; slug: string; count: number }>();
    this.articles.forEach(a => {
      const existing = map.get(a.categorySlug);
      if (existing) existing.count++;
      else map.set(a.categorySlug, { name: a.category, slug: a.categorySlug, count: 1 });
    });
    return Array.from(map.values());
  }

  getAllTags(): string[] {
    const set = new Set<string>();
    this.articles.forEach(a => a.tags.forEach(t => set.add(t)));
    return Array.from(set).sort();
  }
}
