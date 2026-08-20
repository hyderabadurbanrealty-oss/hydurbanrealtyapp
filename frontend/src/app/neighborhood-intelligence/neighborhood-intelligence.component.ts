import {
  Component, Input, OnInit, OnDestroy, AfterViewInit,
  ChangeDetectorRef, NgZone
} from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { PropertyService } from '../services/property.service';

declare const maplibregl: any;

// Category config: key, label, icon, pin colour, emoji
export interface PoiCategory {
  key: string;
  label: string;
  emoji: string;
  color: string;
  icon: string; // emoji shown inside the pin
}

export const POI_CATEGORIES: PoiCategory[] = [
  { key: 'all',           label: 'All',          emoji: '📍', color: '#18215c', icon: 'H'  },
  { key: 'schools',       label: 'Education',    emoji: '🏫', color: '#3b82f6', icon: 'E'  },
  { key: 'hospitals',     label: 'Healthcare',   emoji: '🏥', color: '#ef4444', icon: '+'  },
  { key: 'transport',     label: 'Transport',    emoji: '🚇', color: '#8b5cf6', icon: 'T'  },
  { key: 'shopping',      label: 'Shopping',     emoji: '🛍️', color: '#f59e0b', icon: 'S'  },
  { key: 'entertainment', label: 'Entertainment',emoji: '🎬', color: '#ec4899', icon: 'F'  },
  { key: 'parks',         label: 'Parks',        emoji: '🌳', color: '#10b981', icon: 'P'  },
];

export interface PoiItem {
  name: string;
  type: string;
  distance: string;
  icon: string;
  rating: number;
  lat?: number;
  lng?: number;
  category: string;   // key from POI_CATEGORIES
  _marker?: any;
}

function buildPropertyPin(): string {
  return (
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 44 58" width="44" height="58">` +
    `<ellipse cx="22" cy="56" rx="8" ry="2.5" fill="rgba(0,0,0,0.22)"/>` +
    `<circle cx="22" cy="20" r="20" fill="#18215c" stroke="white" stroke-width="3"/>` +
    `<circle cx="22" cy="20" r="10" fill="white" opacity="0.15"/>` +
    `<text x="22" y="26" text-anchor="middle" font-family="Segoe UI,Arial,sans-serif" font-size="14" font-weight="800" fill="white">H</text>` +
    `<path d="M13 36 L22 58 L31 36 Q22 42 13 36Z" fill="#18215c"/>` +
    `</svg>`
  );
}

function buildPoiPin(color: string, emoji: string, active = false): string {
  const size   = active ? 38 : 30;
  const r      = active ? 14 : 11;
  const stroke = active ? 3 : 2;
  const cx     = size / 2;
  const cy     = size / 2;
  const tailH  = active ? 12 : 9;
  const totalH = size + tailH + 4;
  const fs     = active ? '12' : '9';
  return (
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${size} ${totalH}" width="${size}" height="${totalH}">` +
    `<ellipse cx="${cx}" cy="${totalH - 2}" rx="${size / 4}" ry="2" fill="rgba(0,0,0,0.18)"/>` +
    `<circle cx="${cx}" cy="${cy}" r="${r}" fill="${color}" stroke="white" stroke-width="${stroke}"/>` +
    `<text x="${cx}" y="${cy + 4}" text-anchor="middle" font-family="Segoe UI,Arial,sans-serif" font-size="${fs}">${emoji}</text>` +
    `<path d="M${cx - 5} ${cy + r - 2} L${cx} ${totalH - 4} L${cx + 5} ${cy + r - 2} Q${cx} ${cy + r + 4} ${cx - 5} ${cy + r - 2}Z" fill="${color}"/>` +
    `</svg>`
  );
}

// ── localStorage cache helpers ───────────────────────────────────────────────
const GEOCODE_CACHE_PREFIX  = 'nbhd_gc:';
const NBHD_CACHE_PREFIX     = 'nbhd_data:';
const GEOCODE_TTL_MS        = 30 * 24 * 60 * 60 * 1000;  // 30 days
const NBHD_TTL_MS           = 24 * 60 * 60 * 1000;        // 24 hours

function lsGet<T>(key: string): T | null {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return null;
    const { v, exp } = JSON.parse(raw);
    if (exp && Date.now() > exp) { localStorage.removeItem(key); return null; }
    return v as T;
  } catch { return null; }
}

function lsSet(key: string, value: any, ttlMs: number): void {
  try {
    localStorage.setItem(key, JSON.stringify({ v: value, exp: Date.now() + ttlMs }));
  } catch { /* storage full — skip silently */ }
}

@Component({
  selector: 'app-neighborhood-intelligence',
  templateUrl: './neighborhood-intelligence.component.html',
  styleUrls: ['./neighborhood-intelligence.component.css']
})
export class NeighborhoodIntelligenceComponent implements OnInit, AfterViewInit, OnDestroy {
  @Input() property: any;

  // ── State ────────────────────────────────────────────────────────────────
  dataSource: string = 'loading';  // 'loading' | 'OpenStreetMap' | 'unavailable'
  amenities: any = {};
  activeCategory: string = 'all';
  activePoi: PoiItem | null = null;
  mapReady = false;
  mapId = 'nbhd-map-' + Math.random().toString(36).slice(2, 8);

  readonly categories = POI_CATEGORIES;
  allPois: PoiItem[] = [];
  filteredPois: PoiItem[] = [];

  private map: any = null;
  private propertyMarker: any = null;
  private poiMarkers: any[] = [];
  private propLat: number | null = null;
  private propLng: number | null = null;

  // ── Scores ───────────────────────────────────────────────────────────────
  neighborhoodScore = 0;
  connectivityScore = 0;

  constructor(
    private propertyService: PropertyService,
    private http: HttpClient,
    private cdr: ChangeDetectorRef,
    private zone: NgZone
  ) {}

  ngOnInit(): void {
    if (this.property) {
      this.loadNeighborhoodData();
    }
  }

  ngAfterViewInit(): void {
    // Map init is deferred until data loads so we have a centre coordinate
  }

  ngOnDestroy(): void {
    this.clearPoiMarkers();
    if (this.propertyMarker) { this.propertyMarker.remove(); this.propertyMarker = null; }
    if (this.map) { this.map.remove(); this.map = null; }
  }

  // ── Data loading ─────────────────────────────────────────────────────────
  loadNeighborhoodData(): void {
    const projectId = this.property?.id || this.property?.projectName;
    if (!projectId) { this.setEmpty(); return; }

    // ── 1. Check POI cache first ──────────────────────────────────────────
    const cacheKey = `${NBHD_CACHE_PREFIX}${projectId}`;
    const cached = lsGet<any>(cacheKey);
    if (cached && this.hasRealData(cached)) {
      this.amenities = this.transformApiData(cached);
      this.dataSource = 'OpenStreetMap';
      this.buildPoiList();
      this.calculateScores();
      this.geocodeProperty();
      this.cdr.markForCheck();
      return;
    }

    // ── 2. Fetch from API and cache result ────────────────────────────────
    this.dataSource = 'loading';
    this.propertyService.getNeighborhoodData(projectId, false).subscribe({
      next: (data) => {
        if (data && this.hasRealData(data)) {
          lsSet(cacheKey, data, NBHD_TTL_MS);   // cache the raw API response
          this.amenities = this.transformApiData(data);
          this.dataSource = 'OpenStreetMap';
          this.buildPoiList();
          this.calculateScores();
          this.geocodeProperty();
        } else {
          this.setEmpty();
        }
        this.cdr.markForCheck();
      },
      error: () => { this.setEmpty(); this.cdr.markForCheck(); }
    });
  }

  private setEmpty(): void {
    this.amenities = { schools: [], hospitals: [], transport: [], shopping: [], entertainment: [], parks: [] };
    this.dataSource = 'unavailable';
    this.allPois = [];
    this.filteredPois = [];
  }

  hasRealData(data: any): boolean {
    return (data.schools?.length > 0) || (data.hospitals?.length > 0) || (data.transport?.length > 0);
  }

  private transformApiData(data: any): any {
    // Backend returns each POI with coordinates: { lat, lng } nested.
    // Hoist those to top-level lat/lng so renderPoiPins can use them directly.
    const t = (items: any[], icon: string) =>
      (items || []).map((item: any) => {
        const coords = item.coordinates;
        return {
          ...item,
          lat: coords?.lat ?? item.lat ?? null,
          lng: coords?.lng ?? item.lng ?? null,
          distance: typeof item.distance === 'string'
            ? item.distance
            : `${(item.distance as number)?.toFixed(2) ?? '?'} ${item.distanceUnit || 'km'}`,
          icon,
          rating: item.rating || 0
        };
      });
    return {
      schools:       t(data.schools,       '🏫'),
      hospitals:     t(data.hospitals,     '🏥'),
      transport:     t(data.transport,     '🚇'),
      shopping:      t(data.shopping,      '🛍️'),
      entertainment: t(data.entertainment, '🎬'),
      parks:         t(data.parks,         '🌳')
    };
  }

  private buildPoiList(): void {
    const catKeys: Array<string> = ['schools','hospitals','transport','shopping','entertainment','parks'];
    const seen = new Set<string>();
    const list: PoiItem[] = [];

    catKeys.forEach(key => {
      (this.amenities[key] || []).forEach((p: any) => {
        // Deduplicate by name + rounded coordinates to catch the same place
        // appearing in multiple categories (e.g. restaurants in shopping & entertainment)
        const dedupeKey = `${(p.name || '').toLowerCase()}|${(p.lat ?? 0).toFixed(4)}|${(p.lng ?? 0).toFixed(4)}`;
        if (seen.has(dedupeKey)) return;
        seen.add(dedupeKey);
        list.push({ ...p, category: key });
      });
    });

    // Sort by distance ascending
    list.sort((a, b) => this.parseDistance(a.distance) - this.parseDistance(b.distance));
    this.allPois = list;
    this.filteredPois = list;
  }

  // ── Geocode property then boot the map ───────────────────────────────────
  private geocodeProperty(): void {
    const loc  = this.property['Locality']   || this.property['Village/City/Town'] || '';
    const dist = this.property['District']   || '';
    const pin  = this.property['Pin Code']   || '';
    const str  = this.property['Street']     || '';
    const lmk  = this.property['Land mark']  || '';

    // stable cache key — same scheme as MapCacheService
    const cacheKey = `${GEOCODE_CACHE_PREFIX}${loc}|${dist}|${pin}`.toLowerCase();
    const hit = lsGet<{ lat: number; lng: number }>(cacheKey);
    if (hit?.lat && hit?.lng) {
      this.propLat = hit.lat;
      this.propLng = hit.lng;
      this.initMap();
      return;
    }

    this.geocodeViaService(cacheKey, loc, dist, pin, str, lmk);
  }

  private geocodeViaService(
    cacheKey: string,
    locality: string, district: string, pinCode: string,
    street: string, landmark: string
  ): void {
    this.http.post<{ lat: number; lng: number }>(
      '/api/geocode', { locality, district, pinCode, street, landmark }
    ).subscribe({
      next: (r) => {
        if (r?.lat && r?.lng) {
          this.propLat = r.lat;
          this.propLng = r.lng;
          lsSet(cacheKey, { lat: r.lat, lng: r.lng }, GEOCODE_TTL_MS);
        }
        this.initMap();
      },
      error: () => this.initMap()
    });
  }

  // ── MapLibre init ────────────────────────────────────────────────────────
  private initMap(): void {
    // Wait for the DOM element to exist
    setTimeout(() => {
      const el = document.getElementById(this.mapId);
      if (!el || typeof maplibregl === 'undefined') {
        this.cdr.markForCheck();
        return;
      }

      const center: [number, number] = [
        this.propLng ?? 78.4867,
        this.propLat ?? 17.3850
      ];

      try {
        this.map = new maplibregl.Map({
          container: this.mapId,
          style: 'https://tiles.openfreemap.org/styles/liberty',
          center,
          zoom: 14,
          attributionControl: false
        });

        this.map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
        this.map.addControl(new maplibregl.AttributionControl({ compact: true }), 'bottom-right');

        this.map.on('load', () => {
          this.zone.run(() => {
            this.mapReady = true;
            this.placePropertyPin();
            this.renderPoiPins(this.filteredPois);
            this.cdr.markForCheck();
          });
        });
      } catch (e) {
        console.error('Neighbourhood map init error', e);
      }
    }, 80);
  }

  private placePropertyPin(): void {
    if (!this.map || !this.propLat || !this.propLng) return;

    const el = document.createElement('div');
    el.style.cssText = 'cursor:pointer;';
    el.innerHTML = buildPropertyPin();

    const popup = new maplibregl.Popup({ offset: 25, closeButton: false })
      .setText(this.property['Project Name'] || 'This Property');

    this.propertyMarker = new maplibregl.Marker({ element: el, anchor: 'bottom' })
      .setLngLat([this.propLng, this.propLat])
      .setPopup(popup)
      .addTo(this.map);

    popup.addTo(this.map); // show it by default
  }

  private renderPoiPins(pois: PoiItem[]): void {
    if (!this.map || !this.mapReady) return;
    this.clearPoiMarkers();

    pois.forEach(poi => {
      if (!poi.lat || !poi.lng) return; // skip if no coords from API

      const cat = POI_CATEGORIES.find(c => c.key === poi.category) || POI_CATEGORIES[0];
      const el = document.createElement('div');
      el.style.cssText = 'cursor:pointer;transition:transform 0.15s;';
      el.innerHTML = buildPoiPin(cat.color, cat.icon, false);

      const popup = new maplibregl.Popup({ offset: 20, closeButton: false, className: 'nbhd-popup' })
        .setHTML(`
          <div class="nbhd-pop">
            <strong>${poi.name}</strong>
            <span>${this.formatPlaceType(poi.type)}</span>
            <span class="nbhd-pop-dist">${poi.distance}</span>
          </div>
        `);

      const marker = new maplibregl.Marker({ element: el, anchor: 'bottom' })
        .setLngLat([poi.lng, poi.lat])
        .setPopup(popup)
        .addTo(this.map);

      poi._marker = marker;
      el.addEventListener('mouseenter', () => {
        this.zone.run(() => {
          this.activePoi = poi;
          el.innerHTML = buildPoiPin(cat.color, cat.icon, true);
          this.cdr.markForCheck();
        });
      });
      el.addEventListener('mouseleave', () => {
        this.zone.run(() => {
          if (this.activePoi === poi) this.activePoi = null;
          el.innerHTML = buildPoiPin(cat.color, cat.icon, false);
          this.cdr.markForCheck();
        });
      });
      el.addEventListener('click', () => {
        this.zone.run(() => {
          this.activePoi = poi;
          this.map.flyTo({ center: [poi.lng!, poi.lat!], zoom: 15, speed: 1.2 });
          this.cdr.markForCheck();
        });
      });

      this.poiMarkers.push(marker);
    });
  }

  private clearPoiMarkers(): void {
    this.poiMarkers.forEach(m => m.remove());
    this.poiMarkers = [];
    this.allPois.forEach(p => { p._marker = undefined; });
  }

  // ── Category filter ──────────────────────────────────────────────────────
  selectCategory(key: string): void {
    this.activeCategory = key;
    this.activePoi = null;

    if (key === 'all') {
      this.filteredPois = this.allPois;
    } else {
      this.filteredPois = this.allPois.filter(p => p.category === key);
    }

    if (this.mapReady) {
      this.renderPoiPins(this.filteredPois);
    }
  }

  // ── Card hover / click ───────────────────────────────────────────────────
  onCardHover(poi: PoiItem): void {
    this.activePoi = poi;
    if (poi._marker) {
      const el: HTMLElement = poi._marker.getElement();
      const cat = POI_CATEGORIES.find(c => c.key === poi.category) || POI_CATEGORIES[0];
      el.innerHTML = buildPoiPin(cat.color, cat.icon, true);
    }
  }

  onCardLeave(poi: PoiItem): void {
    if (this.activePoi === poi) this.activePoi = null;
    if (poi._marker) {
      const el: HTMLElement = poi._marker.getElement();
      const cat = POI_CATEGORIES.find(c => c.key === poi.category) || POI_CATEGORIES[0];
      el.innerHTML = buildPoiPin(cat.color, cat.icon, false);
    }
  }

  onCardClick(poi: PoiItem): void {
    this.activePoi = poi;
    if (this.map && poi.lat && poi.lng) {
      this.map.flyTo({ center: [poi.lng, poi.lat], zoom: 15, speed: 1.2 });
      poi._marker?.togglePopup();
    }
  }

  // ── Scores ───────────────────────────────────────────────────────────────
  private calculateScores(): void {
    const a = this.amenities;
    let score = 0;
    score += Math.min((a.schools?.length  || 0) * 7, 25);
    score += Math.min((a.hospitals?.length|| 0) * 7, 20);
    score += Math.min((a.transport?.length|| 0) * 6, 25);
    score += Math.min((a.shopping?.length || 0) * 5, 15);
    score += Math.min(((a.entertainment?.length || 0) + (a.parks?.length || 0)) * 3, 15);
    this.neighborhoodScore = Math.min(Math.round(score), 100);

    const tr = a.transport || [];
    let cs = 0;
    if (tr.some((t: any) => t.type === 'Metro'))   cs += 30;
    if (tr.some((t: any) => t.type === 'Bus'))      cs += 25;
    if (tr.some((t: any) => t.type === 'Train'))    cs += 20;
    if (tr.some((t: any) => t.type === 'Airport'))  cs += 25;
    this.connectivityScore = Math.min(cs, 100);
  }

  getCategoryCount(key: string): number {
    if (key === 'all') return this.allPois.length;
    return this.allPois.filter(p => p.category === key).length;
  }

  getCategoryColor(key: string): string {
    return POI_CATEGORIES.find(c => c.key === key)?.color || '#18215c';
  }

  getScoreColor(score: number): string {
    if (score >= 80) return '#10b981';
    if (score >= 60) return '#3b82f6';
    if (score >= 40) return '#f59e0b';
    return '#ef4444';
  }

  getScoreLabel(score: number): string {
    if (score >= 80) return 'Excellent';
    if (score >= 60) return 'Good';
    if (score >= 40) return 'Average';
    return 'Fair';
  }

  // ── Helpers ──────────────────────────────────────────────────────────────
  parseDistance(distance: string): number {
    if (!distance) return 999;
    const m = distance.match(/(\d+\.?\d*)/);
    return m ? parseFloat(m[1]) : 999;
  }

  getDistanceClass(distance: string): string {
    const d = this.parseDistance(distance);
    if (d <= 1) return 'very-close';
    if (d <= 3) return 'close';
    if (d <= 5) return 'moderate';
    return 'far';
  }

  formatPlaceType(type: string): string {
    if (!type) return '';
    return type.replace(/_/g, ' ')
      .split(' ')
      .map(w => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
      .join(' ');
  }

  trackByName(_: number, p: PoiItem): string {
    return `${p.name}|${p.category}|${p.lat ?? 0}|${p.lng ?? 0}`;
  }
}
