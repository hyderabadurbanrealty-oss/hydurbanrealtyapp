import { Component, OnInit, OnDestroy } from '@angular/core';
import { PropertyService } from '../services/property.service';
import { LoadingService } from '../services/loading.service';
import { CompareService } from '../services/compare.service';
import { Router } from '@angular/router';
import { ChartData, ChartOptions } from 'chart.js';
import { Subscription } from 'rxjs';

@Component({
  selector: 'app-comparison',
  templateUrl: './comparison.component.html',
  styleUrls: ['./comparison.component.css']
})
export class ComparisonComponent implements OnInit, OnDestroy {
  allProperties: any[] = [];
  selectedProperties: any[] = [];
  private compareSub?: Subscription;

  activeTab: 'overview' | 'density' | 'price' = 'overview';

  // Grouped field definitions for Overview tab
  infoFields: any[] = [
    { key: 'averageRating', label: 'Rating', type: 'rating', higherIsBetter: true },
    { key: 'reviewCount', label: 'Reviews', type: 'number', higherIsBetter: true },
    { key: 'proposedNoOfFloors', label: 'Floors', type: 'number' },
    { key: 'proposedNoOfBuildings', label: 'Buildings', type: 'number' },
  ];
  locationFields: any[] = [
    { key: 'Locality', label: 'Locality', type: 'text', fallback: 'locality' },
    { key: 'District', label: 'District', type: 'text', fallback: 'district' },
    { key: 'Plan Approval Number', label: 'RERA Number', type: 'text', fallback: 'registrationNumber' },
    { key: 'Approved Date', label: 'Registered On', type: 'text', fallback: 'dateOfRegistration' },
    { key: 'Proposed Date of Completion', label: 'Expected Completion', type: 'text', fallback: 'proposedDateOfCompletion' },
  ];
  areaFields: any[] = [
    { key: 'Total Area(In sqmts)', label: 'Total Area', type: 'area', higherIsBetter: true, fallback: 'plotArea' },
    { key: 'Net Area(In sqmts)', label: 'Net Area', type: 'area', higherIsBetter: true, fallback: 'approvedPlotArea' },
    { key: 'Approved Built up Area (In Sqmts)', label: 'Built-up Area', type: 'area', fallback: 'builtUpArea' },
  ];

  densityMetricFields: any[] = [
    { key: 'far', label: 'Floor Area Ratio (FAR)', hint: 'lower = more open space', lowerIsBetter: true },
    { key: 'unitsPerHectare', label: 'Units per Hectare', hint: 'lower = less crowded', lowerIsBetter: true },
    { key: 'openSpacePercent', label: 'Open Space %', hint: 'higher = greener', lowerIsBetter: false },
    { key: 'landAreaAcres', label: 'Land Area (Acres)', hint: 'total site area', lowerIsBetter: false },
  ];

  searchTerm: string = '';
  filteredProperties: any[] = [];
  showDropdown: boolean = false;

  // Price trend comparison chart
  priceHistoriesMap: { [id: string]: any[] } = {};
  comparisonChartData: ChartData<'line'> = { labels: [], datasets: [] };
  comparisonChartOptions: ChartOptions<'line'> = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    plugins: {
      legend: {
        display: true,
        position: 'top',
        labels: {
          usePointStyle: true,
          padding: 20,
          font: { size: 13 } as any,
          filter: (item) => !item.text?.includes('(Proj.)')
        }
      },
      tooltip: {
        backgroundColor: 'rgba(15,23,42,0.92)',
        padding: 14,
        cornerRadius: 10,
        boxPadding: 6,
        titleFont: { size: 13, weight: 'bold' } as any,
        bodyFont: { size: 13 } as any,
        callbacks: {
          label: (ctx) => {
            if (ctx.parsed.y == null) return '';
            const suffix = ctx.dataset.label?.includes('(Proj.)') ? ' (projected)' : '';
            return `  ${ctx.dataset.label?.replace(' (Proj.)','') || ''}${suffix}: \u20b9${ctx.parsed.y.toLocaleString('en-IN')}/sqft`;
          }
        }
      }
    },
    scales: {
      x: {
        grid: { color: 'rgba(148,163,184,0.12)' },
        ticks: { font: { size: 12 } as any, color: '#64748b' }
      },
      y: {
        grid: { color: 'rgba(148,163,184,0.12)' },
        ticks: {
          font: { size: 12 } as any,
          color: '#64748b',
          callback: (v) => '\u20b9' + Number(v).toLocaleString('en-IN')
        }
      }
    },
    animation: { duration: 900, easing: 'easeOutQuart' } as any
  };
  hasComparisonChart = false;

  // Color families per property index
  private readonly colorFamilies = [
    ['#3b82f6', '#1d4ed8', '#60a5fa'],
    ['#f59e0b', '#d97706', '#fbbf24'],
    ['#10b981', '#059669', '#34d399']
  ];

  constructor(
    private propertyService: PropertyService,
    private router: Router,
    private loadingService: LoadingService,
    private compareService: CompareService
  ) {}

  ngOnInit(): void {
    this.loadProperties();
    // Pre-populate from the shared compare service (properties added from the grid)
    this.compareSub = this.compareService.list$.subscribe(list => {
      if (list.length > 0) {
        // Merge in any new items not already added, up to 3
        list.forEach(p => {
          const id = (p as any).id || (p as any).projectId;
          const alreadyIn = this.selectedProperties.find(sp =>
            (sp.id && sp.id === id) || (sp.projectId && sp.projectId === id)
          );
          if (!alreadyIn && this.selectedProperties.length < 3) {
            const enriched = { ...p };
            (enriched as any).occupancyDensity = this.computeDensity(p);
            this.selectedProperties.push(enriched);
            if (id && !this.priceHistoriesMap[id]) {
              this.propertyService.getPriceHistory(id).subscribe({
                next: (history) => {
                  this.priceHistoriesMap[id] = Array.isArray(history) ? history : [];
                  this.buildComparisonChart();
                },
                error: () => {
                  this.priceHistoriesMap[id] = [];
                  this.buildComparisonChart();
                }
              });
            }
          }
        });
        this.buildComparisonChart();
      }
    });
  }

  ngOnDestroy(): void {
    this.compareSub?.unsubscribe();
  }

  loadProperties(): void {
    this.propertyService.getProperties().subscribe({
      next: (data) => {
        this.allProperties = data;
        this.filteredProperties = data;
      },
      error: (error) => {
        console.error('Error loading properties:', error);
      }
    });
  }

  onSearchInput(): void {
    const term = this.searchTerm.toLowerCase().trim();
    if (term) {
      this.filteredProperties = this.allProperties.filter(p =>
        p.projectName?.toLowerCase().includes(term) ||
        p.locality?.toLowerCase().includes(term) ||
        p.district?.toLowerCase().includes(term)
      ).slice(0, 10);
      this.showDropdown = true;
    } else {
      this.filteredProperties = this.allProperties;
      this.showDropdown = false;
    }
  }

  addToComparison(property: any): void {
    if (this.selectedProperties.length >= 3) {
      alert('You can compare up to 3 properties only');
      return;
    }
    
    const propertyIdentifier = property.id || property.projectId;
    const isDuplicate = this.selectedProperties.find(p => 
      (p.id && p.id === propertyIdentifier) || 
      (p.projectId && p.projectId === propertyIdentifier)
    );
    
    if (isDuplicate) {
      alert('Property already added for comparison');
      return;
    }

    // Enrich property with computed density metrics from RERA data
    const enriched = { ...property };
    enriched.occupancyDensity = this.computeDensity(property);

    this.selectedProperties.push(enriched);
    this.searchTerm = '';
    this.showDropdown = false;

    // Fetch price history
    if (propertyIdentifier && !this.priceHistoriesMap[propertyIdentifier]) {
      this.propertyService.getPriceHistory(propertyIdentifier).subscribe({
        next: (history) => {
          this.priceHistoriesMap[propertyIdentifier] = Array.isArray(history) ? history : [];
          this.buildComparisonChart();
        },
        error: () => {
          this.priceHistoriesMap[propertyIdentifier] = [];
          this.buildComparisonChart();
        }
      });
    } else {
      this.buildComparisonChart();
    }
  }

  /** Compute density metrics from raw RERA area data */
  private computeDensity(p: any): any {
    const totalArea = parseFloat(p['Total Area(In sqmts)'] || p.totalArea || '0');
    const netArea = parseFloat(p['Net Area(In sqmts)'] || p.netArea || '0');
    const builtUp = parseFloat(p['Approved Built up Area (In Sqmts)'] || p.builtUpArea || '0');
    const totalFlats = parseInt(p.totalFlats || p['Total Flats'] || '0', 10);

    if (!totalArea || totalArea === 0) return { available: false };

    const totalAreaHa = totalArea / 10000;  // sqmt → hectares
    const totalAreaAc = totalArea / 4047;   // sqmt → acres
    const far = builtUp > 0 ? builtUp / totalArea : null;
    const unitsPerHectare = totalFlats > 0 && totalAreaHa > 0 ? Math.round(totalFlats / totalAreaHa) : null;
    const openSpaceRaw = netArea > 0 ? ((netArea - builtUp) / netArea) * 100 : null;
    const openSpacePercent = openSpaceRaw !== null ? Math.max(0, Math.round(openSpaceRaw * 10) / 10) : null;

    // Score: higher = denser/worse for open space
    let densityScore = 0;
    if (far !== null) densityScore += Math.min(far * 20, 40);
    if (unitsPerHectare !== null) densityScore += Math.min(unitsPerHectare / 5, 40);
    if (openSpacePercent !== null) densityScore += Math.max(0, 20 - openSpacePercent / 2);
    densityScore = Math.round(Math.min(100, densityScore));

    const color = densityScore < 35 ? '#10b981' : densityScore < 65 ? '#f59e0b' : '#ef4444';
    const label = densityScore < 35 ? 'Low Density' : densityScore < 65 ? 'Moderate' : 'High Density';
    const farLabel = far !== null ? far.toFixed(2) : 'N/A';

    return {
      available: true,
      score: densityScore,
      color,
      label,
      far,
      farLabel,
      unitsPerHectare,
      openSpacePercent,
      landAreaAcres: Math.round(totalAreaAc * 100) / 100
    };
  }

  removeFromComparison(index: number): void {
    const removed = this.selectedProperties[index];
    if (removed) {
      const id = (removed as any).id || (removed as any).projectId;
      if (id) this.compareService.remove(id);
    }
    this.selectedProperties.splice(index, 1);
    this.buildComparisonChart();
  }

  buildComparisonChart() {
    // Collect all unique month-year labels across all selected properties
    const allDateStrings = new Set<string>();
    this.selectedProperties.forEach(p => {
      const pid = p.id || p.projectId;
      const history = this.priceHistoriesMap[pid] || [];
      history.forEach((e: any) => {
        const label = new Date(e.timestamp ?? e.date).toLocaleDateString('en-IN', { month: 'short', year: 'numeric' });
        allDateStrings.add(label);
      });
    });

    if (allDateStrings.size === 0) {
      this.hasComparisonChart = false;
      return;
    }

    // Sort dates chronologically by parsing them
    const sortedDates = [...allDateStrings].sort((a, b) => {
      const months: any = { Jan:0,Feb:1,Mar:2,Apr:3,May:4,Jun:5,Jul:6,Aug:7,Sep:8,Oct:9,Nov:10,Dec:11 };
      const [ma, ya] = a.split(' ');
      const [mb, yb] = b.split(' ');
      return (Number(ya) - Number(yb)) || (months[ma] - months[mb]);
    });

    // 3 projected months after the last date
    const lastEntryDates = this.selectedProperties
      .map(p => {
        const pid = p.id || p.projectId;
        const hist = this.priceHistoriesMap[pid] || [];
        return hist.length > 0 ? new Date(hist[hist.length - 1]?.timestamp ?? Date.now()) : null;
      })
      .filter(Boolean) as Date[];
    
    const overallLastDate = lastEntryDates.length > 0
      ? new Date(Math.max(...lastEntryDates.map(d => d.getTime())))
      : new Date();

    const projLabels = [1, 2, 3].map(m => {
      const d = new Date(overallLastDate);
      d.setMonth(d.getMonth() + m);
      return d.toLocaleDateString('en-IN', { month: 'short', year: 'numeric' });
    });
    const allLabels = [...sortedDates, ...projLabels];

    const datasets: any[] = [];

    this.selectedProperties.forEach((p, propIdx) => {
      const pid = p.id || p.projectId;
      const history = this.priceHistoriesMap[pid] || [];
      const colors = this.colorFamilies[propIdx % this.colorFamilies.length];
      const propShortName = (p.projectName || '').split(' ').slice(0, 3).join(' ');

      // Collect unit types
      const unitTypes = new Set<string>();
      history.forEach((e: any) => {
        (e?.data?.units ?? []).forEach((u: any) => { if (u.type) unitTypes.add(u.type); });
      });

      [...unitTypes].forEach((type, typeIdx) => {
        const color = colors[typeIdx % colors.length];

        // Map actual data to sorted date labels
        const actualPoints = sortedDates.map(dateStr => {
          const entry = history.find((e: any) =>
            new Date(e.timestamp ?? e.date).toLocaleDateString('en-IN', { month: 'short', year: 'numeric' }) === dateStr
          );
          if (!entry) return null;
          const u = (entry?.data?.units ?? []).find((x: any) => x.type === type);
          return u ? Number(u.pricePerSqft) : null;
        });

        // Linear regression projection
        const valid = actualPoints.filter(v => v !== null) as number[];
        let projected: (number | null)[] = [null, null, null];
        if (valid.length >= 2) {
          const n = valid.length;
          const xMean = (n - 1) / 2;
          const yMean = valid.reduce((a, b) => a + b, 0) / n;
          const slope = valid.reduce((s, y, i) => s + (i - xMean) * (y - yMean), 0)
            / valid.reduce((s, _, i) => s + Math.pow(i - xMean, 2), 0);
          projected = [1, 2, 3].map(m => Math.max(0, Math.round(yMean + slope * (n - 1 + m))));
        }

        // Actual line
        datasets.push({
          label: `${propShortName} · ${type}`,
          data: [...actualPoints, ...Array(3).fill(null)],
          borderColor: color,
          backgroundColor: color + '18',
          borderWidth: 2.5,
          tension: 0.4,
          pointRadius: 5,
          pointHoverRadius: 8,
          pointBackgroundColor: '#fff',
          pointBorderColor: color,
          pointBorderWidth: 2.5,
          fill: true,
          spanGaps: true
        });

        // Projected dashed
        const lastActual = actualPoints[actualPoints.length - 1] ?? (valid.length > 0 ? valid[valid.length - 1] : null);
        datasets.push({
          label: `${propShortName} · ${type} (Proj.)`,
          data: [...Array(actualPoints.length - 1).fill(null), lastActual, ...projected],
          borderColor: color,
          backgroundColor: 'transparent',
          borderDash: [7, 5],
          borderWidth: 2,
          tension: 0.4,
          pointRadius: 4,
          pointHoverRadius: 6,
          pointBackgroundColor: '#fff',
          pointBorderColor: color,
          pointBorderWidth: 2,
          pointStyle: 'triangle',
          fill: false,
          spanGaps: false
        });
      });
    });

    this.comparisonChartData = { labels: allLabels, datasets };
    this.hasComparisonChart = datasets.length > 0;
  }

  getFieldValue(property: any, field: any): any {
    // Try primary key first, then fallback key
    const val = property[field.key];
    if (val !== undefined && val !== null && val !== '') return val;
    if (field.fallback) {
      const fb = property[field.fallback];
      if (fb !== undefined && fb !== null && fb !== '') return fb;
    }
    return null;
  }

  formatArea(value: any): string {
    if (!value || value === 'N/A') return 'N/A';
    return `${value} sq.m`;
  }

  getRatingStars(rating: number): string[] {
    const stars = [];
    const roundedRating = Math.round(rating || 0);
    for (let i = 1; i <= 5; i++) {
      stars.push(i <= roundedRating ? 'full' : 'empty');
    }
    return stars;
  }

  clearComparison(): void {
    this.selectedProperties = [];
    this.priceHistoriesMap = {};
    this.hasComparisonChart = false;
    this.comparisonChartData = { labels: [], datasets: [] };
    this.compareService.clear();
  }

  viewDetails(projectId: string): void {
    this.loadingService.show();
    // Use requestAnimationFrame to ensure loading overlay is painted before navigation
    requestAnimationFrame(() => {
      setTimeout(() => {
        this.router.navigate(['/property', projectId]);
      }, 0);
    });
  }

  goBack(): void {
    this.router.navigate(['/properties']);
  }

  getPropertyColor(index: number): string {
    return this.colorFamilies[index % this.colorFamilies.length][0];
  }

  getNextColor(): string {
    return this.colorFamilies[this.selectedProperties.length % this.colorFamilies.length][0];
  }

  getEmptySlots(): number[] {
    const count = Math.max(0, 3 - this.selectedProperties.length);
    return Array(count).fill(0);
  }

  focusSearch(): void {
    const el = document.querySelector('.search-input') as HTMLInputElement;
    if (el) el.focus();
  }

  isWinner(property: any, field: any): boolean {
    if (!field.higherIsBetter && !field.lowerIsBetter) return false;
    const getVal = (p: any) => parseFloat(p[field.key] ?? p[field.fallback] ?? '');
    const values = this.selectedProperties.map(getVal).filter(v => !isNaN(v));
    if (values.length < 2) return false;
    const val = getVal(property);
    if (isNaN(val)) return false;
    return field.higherIsBetter
      ? val === Math.max(...values)
      : val === Math.min(...values);
  }

  getBarWidth(property: any, field: any): number {
    const getVal = (p: any) => parseFloat(p[field.key] ?? p[field.fallback] ?? '');
    const values = this.selectedProperties.map(getVal).filter(v => !isNaN(v));
    if (values.length === 0) return 0;
    const max = Math.max(...values);
    const val = getVal(property);
    if (isNaN(val) || max === 0) return 0;
    return Math.round((val / max) * 100);
  }

  // ── Density helpers ──────────────────────────────────────────────

  anyHasDensity(): boolean {
    return this.selectedProperties.some(p => p.occupancyDensity?.available);
  }

  getDensityColor(property: any): string {
    return property.occupancyDensity?.color ?? '#64748b';
  }

  anyHasDensityField(key: string): boolean {
    return this.selectedProperties.some(p => {
      const d = p.occupancyDensity;
      return d?.available && d[key] != null;
    });
  }

  getDensityBarWidth(property: any, key: string): number {
    if (!property.occupancyDensity?.available) return 0;
    const values = this.selectedProperties
      .map(p => p.occupancyDensity?.available ? parseFloat(p.occupancyDensity[key]) : NaN)
      .filter(v => !isNaN(v));
    if (values.length === 0) return 0;
    const max = Math.max(...values);
    const val = parseFloat(property.occupancyDensity[key]);
    if (isNaN(val) || max === 0) return 0;
    return Math.round((val / max) * 100);
  }

  getDensityFieldDisplay(property: any, key: string): string {
    if (!property.occupancyDensity?.available) return 'N/A';
    const val = property.occupancyDensity[key];
    if (val == null) return 'N/A';
    if (key === 'far') return property.occupancyDensity.farLabel ?? val.toFixed(2);
    if (key === 'openSpacePercent') return val.toFixed(1) + '%';
    if (key === 'landAreaAcres') return val.toFixed(2) + ' ac';
    if (key === 'unitsPerHectare') return Math.round(val) + '/ha';
    return String(val);
  }
}
