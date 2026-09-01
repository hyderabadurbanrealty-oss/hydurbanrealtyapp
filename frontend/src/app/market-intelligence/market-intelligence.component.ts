import { ChangeDetectorRef, Component, OnInit } from '@angular/core';
import { PropertyService } from '../services/property.service';
import { ChartData, ChartOptions } from 'chart.js';
import { forkJoin, of } from 'rxjs';
import { catchError } from 'rxjs/operators';

@Component({
  standalone: false,
  selector: 'app-market-intelligence',
  templateUrl: './market-intelligence.component.html',
  styleUrls: ['./market-intelligence.component.css']
})
export class MarketIntelligenceComponent implements OnInit {
  Math = Math;
  loading = true;
  allProjects: any[] = [];

  sroLoading = true;
  sroAvailable = false;
  latestQuarter = '';

  priceTrendData: ChartData<'line'> = { labels: [], datasets: [] };
  priceTrendOptions: ChartOptions<'line'> = {
    responsive: true, maintainAspectRatio: false,
    interaction: { mode: 'index' as const, intersect: false },
    plugins: {
      legend: { display: false },
      tooltip: { callbacks: { label: (ctx: any) => ` ₹${Math.round(ctx.parsed.y).toLocaleString('en-IN')}/sqft` } }
    },
    scales: {
      x: { grid: { color: 'rgba(148,163,184,0.08)' }, ticks: { color: '#64748b', font: { size: 11 }, maxRotation: 45 } },
      y: {
        grid: { color: 'rgba(148,163,184,0.08)' },
        ticks: { color: '#64748b', font: { size: 11 }, callback: (v: any) => `₹${(+v / 1000).toFixed(1)}k` }
      }
    }
  };

  volumeTrendData: ChartData<'bar'> = { labels: [], datasets: [] };
  volumeTrendOptions: ChartOptions<'bar'> = {
    responsive: true, maintainAspectRatio: false,
    interaction: { mode: 'index' as const, intersect: false },
    plugins: {
      legend: { display: false },
      tooltip: { callbacks: { label: (ctx: any) => ` ₹${ctx.parsed.y.toLocaleString('en-IN')} Cr` } }
    },
    scales: {
      x: { grid: { display: false }, ticks: { color: '#64748b', font: { size: 11 }, maxRotation: 45 } },
      y: {
        grid: { color: 'rgba(148,163,184,0.08)' },
        ticks: { color: '#64748b', font: { size: 11 }, callback: (v: any) => `₹${v}Cr` }
      }
    }
  };

  countTrendData: ChartData<'bar'> = { labels: [], datasets: [] };
  countTrendOptions: ChartOptions<'bar'> = {
    responsive: true, maintainAspectRatio: false,
    interaction: { mode: 'index' as const, intersect: false },
    plugins: {
      legend: { display: false },
      tooltip: { callbacks: { label: (ctx: any) => ` ${ctx.parsed.y.toLocaleString('en-IN')} transactions` } }
    },
    scales: {
      x: { grid: { display: false }, ticks: { color: '#64748b', font: { size: 11 }, maxRotation: 45 } },
      y: {
        grid: { color: 'rgba(148,163,184,0.08)' },
        ticks: { color: '#64748b', font: { size: 11 }, callback: (v: any) => (+v).toLocaleString('en-IN') }
      }
    }
  };

  priceRankData: ChartData<'bar'> = { labels: [], datasets: [] };
  priceRankOptions: ChartOptions<'bar'> = this._hBarOpts();
  priceRankRows: { locality: string; avg_price_sqft: number; count: number }[] = [];

  volumeRankData: ChartData<'bar'> = { labels: [], datasets: [] };
  volumeRankOptions: ChartOptions<'bar'> = this._hBarOpts();
  volumeRankRows: { locality: string; total_volume: number; count: number }[] = [];

  countRankData: ChartData<'bar'> = { labels: [], datasets: [] };
  countRankOptions: ChartOptions<'bar'> = this._hBarOpts();
  countRankRows: { locality: string; count: number }[] = [];

  // Entity selector (city-wide or per locality)
  sroLocalities: string[] = [];
  selectedEntity = 'Hyderabad';
  private _localityAgg: any = null;
  private _localityRevMap = new Map<string, string>();

  // Header KPIs
  cityAvgSqft = 0;
  prevAvgSqft = 0;
  yoyChange = 0;
  latestCount = 0;
  latestVolumeCr = 0;

  // ── Ready Reckoner / Circle Rates ─────────────────────────────────
  rrLoading = true;
  rrAvailable = false;
  rrDistrict = 'All';
  rrDistricts: string[] = [];
  rrAllRows: any[] = [];   // full summary from API
  rrRows: any[] = [];   // filtered
  rrChartData: ChartData<'bar'> = { labels: [], datasets: [] };
  rrChartOptions: ChartOptions<'bar'> = {
    indexAxis: 'y', responsive: true, maintainAspectRatio: false,
    plugins: {
      legend: { display: true, position: 'top', labels: { color: '#475569', font: { size: 12 }, boxWidth: 14 } },
      tooltip: {
        mode: 'index', intersect: false,
        callbacks: { label: (ctx: any) => ` ${ctx.dataset.label}: ₹${(ctx.parsed.x || 0).toLocaleString('en-IN')}/sqft` }
      }
    },
    scales: {
      x: {
        grid: { color: 'rgba(148,163,184,0.12)' }, ticks: {
          color: '#64748b', font: { size: 11 },
          callback: (v: any) => `₹${(+v / 1000).toFixed(0)}k`
        }
      },
      y: { grid: { display: false }, ticks: { color: '#1e293b', font: { size: 12 } } }
    }
  };

  // Entity-specific latest-quarter stats (update on entity selector change)
  entityLatestSqft = 0;
  entityLatestVolCr = 0;
  entityLatestCount = 0;
  entityYoyChange = 0;

  // Circle Rate vs Market Price comparison
  rrVsMarketData: ChartData<'bar'> = { labels: [], datasets: [] };
  rrVsMarketOptions: ChartOptions<'bar'> = {
    indexAxis: 'y', responsive: true, maintainAspectRatio: false,
    plugins: {
      legend: {
        display: true, position: 'top' as const,
        labels: { color: '#94a3b8', font: { size: 11 }, boxWidth: 14 }
      },
      tooltip: { callbacks: { label: (ctx: any) => ` ₹${ctx.parsed.x.toLocaleString('en-IN')}/sqft` } }
    },
    scales: {
      x: {
        grid: { color: 'rgba(148,163,184,0.12)' }, ticks: {
          color: '#64748b', font: { size: 11 },
          callback: (v: any) => `₹${((+v) / 1000).toFixed(0)}k`
        }
      },
      y: { grid: { display: false }, ticks: { color: '#1e293b', font: { size: 12 } } }
    }
  };
  rrVsMarketRows: { locality: string; circle: number; market: number; premium: number }[] = [];

  constructor(
    private propertyService: PropertyService,
    private cdr: ChangeDetectorRef
  ) { }

  ngOnInit(): void {
    forkJoin({
      projects: this.propertyService.getProperties().pipe(catchError(() => of([]))),
      cityAgg: this.propertyService.getSroCityAggregate().pipe(catchError(() => of(null))),
      localityAgg: this.propertyService.getSroLocalityAggregate().pipe(catchError(() => of(null))),
      priceRank: this.propertyService.getSroPriceRank().pipe(catchError(() => of(null))),
      volRank: this.propertyService.getSroVolumeRank().pipe(catchError(() => of(null))),
      unitRates: this.propertyService.getUnitRatesSummary().pipe(catchError(() => of([])))
    }).subscribe(({ projects, cityAgg, localityAgg, priceRank, volRank, unitRates }) => {
      this.allProjects = projects as any[];
      this._localityAgg = localityAgg;
      setTimeout(() => {
        this.buildSroCharts(cityAgg, priceRank, volRank);
        this.buildUnitRatesChart(unitRates as any[]);
        this.buildRrVsMarket();
        this.loading = false;
        this.sroLoading = false;
        this.rrLoading = false;
        this.cdr.detectChanges();
      }, 0);
    });
  }

  buildSroCharts(cityAgg: any, priceRankRes: any, volRankRes: any) {
    if (!cityAgg || Object.keys(cityAgg).length === 0) { this.sroAvailable = false; return; }
    this.sroAvailable = true;
    const quarters = Object.keys(cityAgg).sort();
    this.latestQuarter = quarters[quarters.length - 1] || '';

    // Header KPIs: latest quarter + YoY change
    const latestQ = cityAgg[this.latestQuarter];
    this.cityAvgSqft = latestQ?.avg_price_sqft ?? 0;
    this.latestCount = latestQ?.count ?? 0;
    this.latestVolumeCr = Math.round((latestQ?.total_volume ?? 0) / 1e5) / 10;
    const yoyQ = quarters.length >= 5 ? quarters[quarters.length - 5] : null;
    this.prevAvgSqft = yoyQ ? (cityAgg[yoyQ]?.avg_price_sqft ?? 0) : 0;
    this.yoyChange = this.prevAvgSqft > 0
      ? Math.round((this.cityAvgSqft - this.prevAvgSqft) / this.prevAvgSqft * 1000) / 10
      : 0;

    // Build locality list for entity selector (normalized names)
    if (this._localityAgg) {
      this._localityRevMap.clear();
      this.sroLocalities = Object.keys(this._localityAgg)
        .map(orig => { const norm = this._normLoc(orig); this._localityRevMap.set(norm, orig); return norm; })
        .filter((v, i, a) => a.indexOf(v) === i)
        .sort();
    }

    this._buildTrendCharts(cityAgg);

    if (priceRankRes?.rank?.length) {
      this.priceRankRows = priceRankRes.rank.map((r: any) => ({...r, locality: this._normLoc(r.locality)}));
      const pv = this.priceRankRows.map(r => r.avg_price_sqft); const pm = Math.max(...pv, 1);
      this.priceRankData = {
        labels: this.priceRankRows.map(r => r.locality), datasets: [{
          data: pv,
          backgroundColor: pv.map(v => `rgba(99,102,241,${+(0.35 + 0.65 * v / pm).toFixed(2)})`),
          borderColor: '#6366f1', borderWidth: 1.5, borderRadius: 4
        }]
      };
    }

    if (volRankRes?.rank?.length) {
      // Normalize locality names then merge duplicates by summing volume & count
      const rawVolRows: { locality: string; total_volume: number; count: number }[] =
        volRankRes.rank.map((r: any) => ({...r, locality: this._normLoc(r.locality)}));
      const volMergeMap = new Map<string, { total_volume: number; count: number }>();
      for (const r of rawVolRows) {
        const existing = volMergeMap.get(r.locality);
        if (existing) {
          existing.total_volume += r.total_volume;
          existing.count        += r.count;
        } else {
          volMergeMap.set(r.locality, { total_volume: r.total_volume, count: r.count });
        }
      }
      this.volumeRankRows = Array.from(volMergeMap.entries())
        .map(([locality, d]) => ({ locality, total_volume: d.total_volume, count: d.count }))
        .sort((a, b) => b.total_volume - a.total_volume)
        .slice(0, 10);

      const vv = this.volumeRankRows.map(r => Math.round(r.total_volume / 1e5) / 10);
      const vm = Math.max(...vv, 1);
      this.volumeRankData = {
        labels: this.volumeRankRows.map(r => r.locality), datasets: [{
          data: vv,
          backgroundColor: vv.map(v => `rgba(16,185,129,${+(0.35 + 0.65 * v / vm).toFixed(2)})`),
          borderColor: '#10b981', borderWidth: 1.5, borderRadius: 4
        }]
      };

      // Count Rank: re-sort the already-merged rows by deal count
      this.countRankRows = [...this.volumeRankRows]
        .sort((a, b) => b.count - a.count)
        .map(r => ({ locality: r.locality, count: r.count }));
      const cv = this.countRankRows.map(r => r.count); const cm = Math.max(...cv, 1);
      this.countRankData = {
        labels: this.countRankRows.map(r => r.locality), datasets: [{
          data: cv,
          backgroundColor: cv.map(v => `rgba(245,158,11,${+(0.35 + 0.65 * v / cm).toFixed(2)})`),
          borderColor: '#f59e0b', borderWidth: 1.5, borderRadius: 4
        }]
      };
    }
  }

  onEntityChange(entity: string) {
    this.selectedEntity = entity;
    const origKey = this._localityRevMap.get(entity) || entity;
    if (entity === 'Hyderabad' || !this._localityAgg?.[origKey]) {
      this.propertyService.getSroCityAggregate().subscribe({
        next: (agg: any) => this._buildTrendCharts(agg),
        error: () => { }
      });
    } else {
      this._buildTrendCharts(this._localityAgg[origKey]);
    }
  }

  _normLoc(raw: string): string {
    if (!raw) return raw;
    const r = raw.toUpperCase();
    if (r.includes('KONDAPUR'))                                return 'Kondapur';
    if (r.includes('NARSINGI'))                                return 'Narsingi';
    if (r.includes('GACHIBOWLI'))                              return 'Gachibowli';
    if (r.includes('PUPPALGUDA') || r.includes('PUPPAL'))      return 'Puppalguda';
    if (r.includes('NALAGANDLA') || r.includes('NALLAGANDLA')) return 'Nalagandla';
    if (r.includes('KUKATPALLY') || r.includes('KUKATPAL'))   return 'Kukatpally';
    if (r.includes('KOKAPET'))                                 return 'Kokapet';
    if (r.includes('MADHAPUR') || r.includes('MADEENAGUDA'))  return 'Madhapur';
    if (r.includes('MANIKONDA'))                               return 'Manikonda';
    if (r.includes('AMEENPUR') || r.includes('AMEENPOOR'))    return 'Ameenpur';
    if (r.includes('CHANDANAGAR'))                             return 'Chandanagar';
    if (r.includes('MIYAPUR'))                                 return 'Miyapur';
    if (r.includes('BACHUPALLY'))                              return 'Bachupally';
    if (r.includes('NIZAMPET'))                                return 'Nizampet';
    if (r.includes('TELLAPUR'))                                return 'Tellapur';
    if (r.includes('KOMPALLY'))                                return 'Kompally';
    if (r.includes('SERILINGAMP') || r.includes('HITECH CITY')) return 'Hi-Tech City';
    if (r.includes('OSMAN NAGAR') || r.includes('OSMANGUDA')) return 'Osman Nagar';
    if (r.includes('UPPAL'))                                   return 'Uppal';
    if (r.includes('LB NAGAR') || r.includes('LBNAGAR'))      return 'LB Nagar';
    if (r.includes('BANJARA'))                                 return 'Banjara Hills';
    if (r.includes('JUBILEE'))                                 return 'Jubilee Hills';
    if (r.includes('GOPANPALLE') || r.includes('GOPANPAL'))   return 'Gopanpalle';
    if (r.includes('MANCHIREVULA'))                            return 'Manchirevula';
    if (r.includes('NEKNAMPUR'))                               return 'Neknampur';
    if (r.includes('KOTHAGUDA'))                               return 'Kothaguda';
    if (r.includes('RAIDURG') || r.includes('RAIDURGAM'))     return 'Raidurg';
    if (r.includes('NANAKRAMGUDA'))                            return 'Nanakramguda';
    // Fallback: title-case first word
    return raw.charAt(0).toUpperCase() + raw.slice(1).toLowerCase();
  }

  private _buildTrendCharts(agg: any) {
    const quarters = Object.keys(agg).sort();
    const labels = quarters.map(q => this._fmtQ(q));
    const latestQ = quarters[quarters.length - 1] || '';
    const prevYearQ = quarters.length >= 5 ? quarters[quarters.length - 5] : null;
    this.entityLatestSqft = agg[latestQ]?.avg_price_sqft ?? 0;
    this.entityLatestVolCr = Math.round((agg[latestQ]?.total_volume ?? 0) / 1e5) / 10;
    this.entityLatestCount = agg[latestQ]?.count ?? 0;
    const prevSqft = prevYearQ ? (agg[prevYearQ]?.avg_price_sqft ?? 0) : 0;
    this.entityYoyChange = prevSqft > 0
      ? Math.round((this.entityLatestSqft - prevSqft) / prevSqft * 1000) / 10 : 0;
    this.priceTrendData = {
      labels, datasets: [{
        label: 'Avg ₹/sqft',
        data: quarters.map(q => agg[q]?.avg_price_sqft ? Math.round(agg[q].avg_price_sqft) : null),
        borderColor: '#6366f1', backgroundColor: 'rgba(99,102,241,0.12)',
        borderWidth: 2.5, tension: 0.4, pointRadius: 4, pointHoverRadius: 7,
        pointBackgroundColor: '#6366f1', fill: true, spanGaps: true
      }]
    };
    this.volumeTrendData = {
      labels, datasets: [{
        label: 'Volume (₹ Cr)',
        data: quarters.map(q => Math.round((agg[q]?.total_volume ?? 0) / 1e5) / 10),
        backgroundColor: quarters.map((q, i) => i === quarters.length - 1 ? 'rgba(16,185,129,0.9)' : 'rgba(16,185,129,0.55)'),
        borderColor: '#10b981', borderWidth: 1.5, borderRadius: 4
      }]
    };
    this.countTrendData = {
      labels, datasets: [{
        label: 'Transactions',
        data: quarters.map(q => agg[q]?.count ?? 0),
        backgroundColor: quarters.map((q, i) => i === quarters.length - 1 ? 'rgba(245,158,11,0.9)' : 'rgba(245,158,11,0.55)'),
        borderColor: '#f59e0b', borderWidth: 1.5, borderRadius: 4
      }]
    };
  }

  _fmtQ(q: string): string {
    // "Q1 2024" → "Q1'24"
    const m = q.match(/^(Q[1-4])\s+(\d{4})$/);
    return m ? `${m[1]}'${m[2].slice(2)}` : q;
  }

  buildUnitRatesChart(rows: any[]) {
    if (!rows || rows.length === 0) { this.rrAvailable = false; return; }
    this.rrAvailable = true;
    this.rrAllRows = rows;
    const districts = [...new Set(rows.map((r: any) => r.district).filter(Boolean))].sort();
    this.rrDistricts = districts;
    this._applyRrFilter();
  }

  onRrDistrictChange(d: string) { this.rrDistrict = d; this._applyRrFilter(); }

  private _applyRrFilter() {
    const filtered = this.rrDistrict === 'All'
      ? this.rrAllRows
      : this.rrAllRows.filter((r: any) => r.district === this.rrDistrict);

    // Sort by apartment rate desc (fall back to land if no apartment)
    const top = [...filtered]
      .sort((a: any, b: any) => (b.apartment_rate_sqft || b.avg_rate_sqft || 0) - (a.apartment_rate_sqft || a.avg_rate_sqft || 0))
      .slice(0, 20);
    this.rrRows = [...filtered].sort((a: any, b: any) => (b.apartment_rate_sqft || b.avg_rate_sqft || 0) - (a.apartment_rate_sqft || a.avg_rate_sqft || 0));

    const labels      = top.map((r: any) => r.mandal || r.locality);
    const aptRates    = top.map((r: any) => r.apartment_rate_sqft || r.avg_rate_sqft || null);
    const landRates   = top.map((r: any) => r.land_rate_sqft || null);
    const hasLand     = landRates.some(v => v !== null);

    const datasets: any[] = [
      {
        label: 'Apartment Value (₹/sqft)',
        data: aptRates,
        backgroundColor: 'rgba(99,102,241,0.75)',
        borderColor: '#6366f1', borderWidth: 1.5, borderRadius: 4,
      }
    ];
    if (hasLand) {
      datasets.push({
        label: 'Land Value (₹/sqft)',
        data: landRates,
        backgroundColor: 'rgba(16,185,129,0.65)',
        borderColor: '#10b981', borderWidth: 1.5, borderRadius: 4,
      });
    }

    this.rrChartData = { labels, datasets };
  }

  buildRrVsMarket() {
    if (!this.priceRankRows.length || !this.rrAllRows.length) return;

    // SRO data is village-level; RR data is mandal-level.
    // Map each normalized display locality → its IGRS revenue mandal name.
    // Serilingampalli SRO covers multiple mandals: Gandipet, Rajendranagar & Serilingampally.
    const LOCALITY_TO_MANDAL: Record<string, string> = {
      // Gandipet mandal (SW Hyderabad) — RR has GANDIPET ✅
      'Kokapet':      'GANDIPET',
      'Narsingi':     'GANDIPET',
      'Puppalguda':   'GANDIPET',
      'Neknampur':    'GANDIPET',
      'Tellapur':     'GANDIPET',
      'Osman Nagar':  'GANDIPET',
      // Rajendranagar mandal — RR has RAJENDRANAGAR ✅
      'Manikonda':    'RAJENDRANAGAR',
      'Manchirevula': 'RAJENDRANAGAR',
      'LB Nagar':     'RAJENDRANAGAR',
      // Serilingampally mandal (Hi-Tech City / Gachibowli belt) — needs RR re-scrape
      'Nalagandla':   'SERILINGAMPALLE',
      'Gachibowli':   'SERILINGAMPALLE',
      'Kondapur':     'SERILINGAMPALLE',
      'Madhapur':     'SERILINGAMPALLE',
      'Raidurg':      'SERILINGAMPALLE',
      'Gopanpalle':   'SERILINGAMPALLE',
      'Nanakramguda': 'SERILINGAMPALLE',
      'Hi-Tech City': 'SERILINGAMPALLE',
      // Balanagar / Medchal-Malkajgiri mandals — RR has both ✅
      'Chandanagar':  'BALANAGAR',
      'Kompally':     'BALANAGAR',
      'Bachupally':   'BACHUPALLY',
      'Nizampet':     'BACHUPALLY',
      'Miyapur':      'BACHUPALLY',
      // Sangareddy district — RR has AMEENPUR ✅
      'Ameenpur':     'AMEENPUR',
      // Hyderabad dist mandals — RR has SHAIKPET, AMEERPET ✅
      'Banjara Hills':'SHAIKPET',
      'Jubilee Hills':'SHAIKPET',
      'Kukatpally':   'AMEERPET',
      'Uppal':        'UPPAL',
    };

    // Build mandal → avg circle rate map from RR summary rows
    const mandalCircleMap = new Map<string, number>();
    for (const r of this.rrAllRows) {
      const mandal = (r.mandal || '').trim().toUpperCase();
      const rate = Math.round(r.apartment_rate_sqft || r.avg_rate_sqft || 0);
      if (mandal && rate > 0 && !mandalCircleMap.has(mandal)) {
        mandalCircleMap.set(mandal, rate);
      }
    }

    const seen = new Set<string>();
    const matched: { locality: string; circle: number; market: number; premium: number }[] = [];
    for (const r of this.priceRankRows) {
      const loc = r.locality;
      if (seen.has(loc)) continue;
      const mandal = LOCALITY_TO_MANDAL[loc] || loc.trim().toUpperCase();
      const circle = mandalCircleMap.get(mandal) || 0;
      if (circle > 0) {
        seen.add(loc);
        const market = Math.round(r.avg_price_sqft);
        const premium = Math.round((market - circle) / circle * 100);
        matched.push({ locality: loc, circle, market, premium });
      }
    }
    const top = matched.sort((a, b) => b.market - a.market).slice(0, 15);
    this.rrVsMarketRows = top;
    if (!top.length) return;
    const labels = top.map(r => r.locality);
    const markets = top.map(r => r.market);
    const circles = top.map(r => r.circle);
    this.rrVsMarketData = {
      labels, datasets: [
        {
          label: 'Market Price (SRO)', data: markets,
          backgroundColor: 'rgba(99,102,241,0.75)', borderColor: '#6366f1', borderWidth: 1.5, borderRadius: 4
        },
        {
          label: 'Circle Rate (IGRS RR)', data: circles,
          backgroundColor: 'rgba(124,58,237,0.4)', borderColor: '#7c3aed', borderWidth: 1.5, borderRadius: 4
        }
      ]
    };
  }

  private _hBarOpts(): ChartOptions<'bar'> {
    return {
      indexAxis: 'y', responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { color: 'rgba(148,163,184,0.12)' }, ticks: { color: '#64748b', font: { size: 11 } } },
        y: { grid: { display: false }, ticks: { color: '#1e293b', font: { size: 12 } } }
      }
    };
  }
}
