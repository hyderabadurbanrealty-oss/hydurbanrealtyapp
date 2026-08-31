import {
  Component, OnInit, OnDestroy, AfterViewInit,
  ChangeDetectorRef, NgZone, ChangeDetectionStrategy
} from '@angular/core';
import { Router } from '@angular/router';
import { PropertyService } from '../services/property.service';
import { MapCacheService } from '../services/map-cache.service';
import { Property } from '../map/map.component';
import { environment } from '../../environments/environment';
import { Subject } from 'rxjs';
import { debounceTime, distinctUntilChanged, takeUntil } from 'rxjs/operators';

declare const maplibregl: any;

export interface MappedProperty extends Property {
  lat: number;
  lng: number;
  _geocoded?: boolean;
  _marker?: any;
}

type MapStyle = 'street' | 'satellite' | 'dark';

// Raw GL style objects using OpenFreeMap — bypasses Mapbox token validation
// since no mapbox.com tile URLs are involved
const STYLE_URLS: Record<MapStyle, string> = {
  street:    'https://tiles.openfreemap.org/styles/liberty',
  satellite: 'https://tiles.openfreemap.org/styles/positron',
  dark:      'https://tiles.openfreemap.org/styles/dark'
};

// Color per status — used both in CSS and in dynamic SVG pins
const PIN_COLORS: Record<string, string> = {
  completed: '#10b981',
  ongoing:   '#3b82f6',
  new:       '#f59e0b',
  default:   '#18215c'
};

function buildPinSvg(fill: string, label: string): string {
  const enc = encodeURIComponent(fill);
  const letter = label ? label[0].toUpperCase() : '•';
  return (
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 36 48" width="36" height="48">` +
    // shadow ellipse
    `<ellipse cx="18" cy="46" rx="7" ry="2" fill="rgba(0,0,0,0.18)"/>` +
    // body circle
    `<circle cx="18" cy="18" r="17" fill="${fill}" stroke="white" stroke-width="2.5"/>` +
    // inner white dot
    `<circle cx="18" cy="18" r="7" fill="white" opacity="0.9"/>` +
    // letter
    `<text x="18" y="23" text-anchor="middle" font-family="Segoe UI,Arial,sans-serif" ` +
      `font-size="11" font-weight="700" fill="${fill}">${letter}</text>` +
    // pointer
    `<path d="M11 31 L18 48 L25 31 Q18 36 11 31Z" fill="${fill}"/>` +
    `</svg>`
  );
}

@Component({
  standalone: false,
  selector: 'app-map-view',
  templateUrl: './map-view.component.html',
  styleUrls: ['./map-view.component.css'],
  changeDetection: ChangeDetectionStrategy.Default
})
export class MapViewComponent implements OnInit, AfterViewInit, OnDestroy {

  // ── State ──────────────────────────────────────────────────────────────
  allProperties:      Property[]       = [];
  mappedProperties:   MappedProperty[] = [];
  filteredProperties: MappedProperty[] = [];
  selectedProperty:   MappedProperty | null = null;

  dataLoading       = true;   // API fetch in progress
  geocoding         = false;  // geocoding in progress (non-blocking)
  geocodingProgress = 0;
  geocodingTotal    = 0;
  geocodeCacheHits  = 0;      // how many were resolved from cache instantly
  mapReady          = false;
  sidebarOpen       = true;
  activeStyle: MapStyle = 'street';

  // ── Location detection ────────────────────────────────────────────────
  locationState: 'prompt' | 'requesting' | 'granted' | 'denied' | 'unavailable' = 'prompt';
  userCity = '';
  userLat: number | null = null;
  userLng: number | null = null;

  // ── Schedule Visit modal ──────────────────────────────────────────────
  showVisitModal   = false;
  visitProjectName = '';
  visitProjectId   = '';

  // ── Filters ────────────────────────────────────────────────────────────
  searchQuery      = '';
  selectedDistrict = '';
  selectedStatus   = '';
  selectedType     = '';
  sortBy           = 'name';

  districts: string[] = [];
  statuses:  string[] = [];
  types:     string[] = [];

  // ── Internal ───────────────────────────────────────────────────────────
  private map: any;
  private markers:         any[]             = [];
  private markerQueue:     MappedProperty[]  = []; // pins waiting for map to be ready
  private destroy$         = new Subject<void>();
  private searchSubject    = new Subject<string>();
  private activePopup:     any = null;

  private readonly DEFAULT_CENTER: [number, number] = [78.4867, 17.3850];
  private readonly DEFAULT_ZOOM = 11;

  constructor(
    private propertyService: PropertyService,
    private mapCache: MapCacheService,
    private cdr: ChangeDetectorRef,
    private zone: NgZone,
    private router: Router
  ) {}

  // ── Lifecycle ──────────────────────────────────────────────────────────
  ngOnInit(): void {
    this.searchSubject.pipe(
      debounceTime(280),
      distinctUntilChanged(),
      takeUntil(this.destroy$)
    ).subscribe(() => this.applyFilters());
  }

  ngAfterViewInit(): void {
    // Map renders first — data loads in parallel
    setTimeout(() => {
      this.initMap();
      this.loadProperties();   // starts after map init is queued
    }, 0);
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
    this.clearMarkers();
    if (this.map) this.map.remove();
  }

  // ── Location detection ────────────────────────────────────────────────

  /** Called when user clicks "Allow" in our prompt banner */
  requestLocation(): void {
    if (!navigator.geolocation) {
      this.locationState = 'unavailable';
      this.cdr.markForCheck();
      return;
    }
    this.locationState = 'requesting';
    this.cdr.markForCheck();

    navigator.geolocation.getCurrentPosition(
      (pos) => this.zone.run(() => this.onLocationGranted(pos)),
      (err) => this.zone.run(() => this.onLocationDenied(err)),
      { timeout: 10000, maximumAge: 5 * 60 * 1000 }
    );
  }

  dismissLocation(): void {
    this.locationState = 'denied';
    this.cdr.markForCheck();
  }

  private async onLocationGranted(pos: GeolocationPosition): Promise<void> {
    this.userLat = pos.coords.latitude;
    this.userLng = pos.coords.longitude;
    this.locationState = 'granted';

    // Reverse geocode to get city name (using our backend proxy)
    try {
      const resp = await fetch(
        `https://nominatim.openstreetmap.org/reverse?lat=${this.userLat}&lon=${this.userLng}&format=json`,
        { headers: { 'Accept-Language': 'en' } }
      );
      if (resp.ok) {
        const data = await resp.json();
        this.userCity = data?.address?.city
          || data?.address?.town
          || data?.address?.suburb
          || data?.address?.county
          || 'your location';
      }
    } catch {
      this.userCity = 'your location';
    }

    // Fly the map to user's position
    if (this.map) {
      this.map.flyTo({
        center: [this.userLng!, this.userLat!],
        zoom: 13,
        speed: 1.6,
        curve: 1.4
      });
    }

    // Add a pulsing "You are here" marker
    this.addUserLocationMarker(this.userLat!, this.userLng!);

    this.cdr.markForCheck();
  }

  private onLocationDenied(err: GeolocationPositionError): void {
    this.locationState = err.code === 1 ? 'denied' : 'unavailable';
    this.cdr.markForCheck();
  }

  private addUserLocationMarker(lat: number, lng: number): void {
    if (!this.map || !this.mapReady) return;

    const el = document.createElement('div');
    el.className = 'user-location-marker';
    el.innerHTML = `
      <div class="ulm-pulse"></div>
      <div class="ulm-dot"></div>
    `;

    new maplibregl.Marker({ element: el, anchor: 'center' })
      .setLngLat([lng, lat])
      .addTo(this.map);
  }

  // ── Map Init ──────────────────────────────────────────────────────────
  private initMap(): void {
    try {
      this.map = new maplibregl.Map({
        container: 'map-container',
        style: STYLE_URLS.street,
        center: this.DEFAULT_CENTER,
        zoom: this.DEFAULT_ZOOM,
        attributionControl: false
      });

      this.map.addControl(new maplibregl.NavigationControl({ showCompass: true }), 'bottom-right');
      this.map.addControl(new maplibregl.ScaleControl({ maxWidth: 120, unit: 'metric' }), 'bottom-left');
      this.map.addControl(
        new maplibregl.GeolocateControl({
          positionOptions: { enableHighAccuracy: true },
          trackUserLocation: false,
          showAccuracyCircle: false
        }),
        'bottom-right'
      );
      this.map.addControl(new maplibregl.AttributionControl({ compact: true }), 'bottom-right');

      this.map.on('click', () => {
        this.zone.run(() => {
          this.closePopup();
          this.selectedProperty = null;
          this.cdr.markForCheck();
        });
      });

      this.map.on('load', () => {
        this.map.resize();
        this.zone.run(() => {
          this.mapReady = true;
          this.cdr.markForCheck();
          // Flush any pins that were geocoded before the map was ready
          this.flushMarkerQueue();
        });
      });
    } catch (e) {
      console.error('Map init error', e);
    }
  }

  // ── Style switcher ────────────────────────────────────────────────────
  setStyle(style: MapStyle): void {
    if (this.activeStyle === style) return;
    this.activeStyle = style;
    if (!this.map) return;
    this.map.setStyle(STYLE_URLS[style]);
    this.map.once('styledata', () => { this.renderMarkers(); });
  }

  // ── Data ──────────────────────────────────────────────────────────────
  private loadProperties(): void {
    this.dataLoading = true;
    this.mapCache.getProperties().pipe(
      takeUntil(this.destroy$)
    ).subscribe({
      next: (props) => {
        this.allProperties = props;
        this.buildFilterOptions(props);
        this.dataLoading = false;
        this.cdr.markForCheck();
        this.geocodeAll(props);
      },
      error: () => { this.dataLoading = false; this.cdr.markForCheck(); }
    });
  }

  private buildFilterOptions(props: Property[]): void {
    const districts = new Set<string>();
    const statuses  = new Set<string>();
    const types     = new Set<string>();
    props.forEach(p => {
      if (p['District'])       districts.add(p['District']);
      if (p['Project Status']) statuses.add(p['Project Status']);
      if (p['Project Type'])   types.add(p['Project Type']);
    });
    this.districts = Array.from(districts).sort();
    this.statuses  = Array.from(statuses).sort();
    this.types     = Array.from(types).sort();
  }

  // ── Geocoding ─────────────────────────────────────────────────────────
  private async geocodeAll(props: Property[]): Promise<void> {
    this.geocoding         = true;
    this.geocodingTotal    = props.length;
    this.geocodingProgress = 0;
    this.geocodeCacheHits  = 0;

    // Pass 1 — resolve everything already in cache instantly (no network)
    const uncached: Property[] = [];
    props.forEach(p => {
      const key = this.geocodeKey(p);
      if (this.mapCache.hasGeocode(key)) {
        const cached = this.mapCache.getGeocode(key);
        if (cached) {
          const mapped: MappedProperty = { ...p, lat: cached.lat, lng: cached.lng, _geocoded: true };
          this.mappedProperties.push(mapped);
          // Always queue — flush handles both ready and not-ready cases
          this.markerQueue.push(mapped);
          this.geocodeCacheHits++;
        }
        this.geocodingProgress++;
      } else {
        uncached.push(p);
      }
    });

    // Flush queue now if map is already ready; otherwise map.on('load') will flush it
    this.zone.run(() => {
      if (this.mapReady && this.markerQueue.length > 0) {
        this.flushMarkerQueue();
      }
      this.applyFiltersNoRemap();
      this.cdr.markForCheck();
    });

    // Pass 2 — geocode remaining via Nominatim in batches
    const BATCH = 5;
    for (let i = 0; i < uncached.length; i += BATCH) {
      if (this.destroy$.isStopped) return;

      const batch = uncached.slice(i, i + BATCH);
      const done  = await Promise.all(batch.map(p => this.geocodeProperty(p)));

      this.zone.run(() => {
        done.forEach(r => {
          if (!r) return;
          this.mappedProperties.push(r);
          if (this.mapReady) {
            // Map is ready — place directly
            if (this.matchesFilters(r)) this.placeMarkerOnMap(r);
          } else {
            // Map not ready yet — queue for flush on load
            this.markerQueue.push(r);
          }
        });
        this.geocodingProgress = Math.min(
          this.geocodingProgress + BATCH, props.length
        );
        this.applyFiltersNoRemap();
        this.cdr.markForCheck();
      });

      if (i + BATCH < uncached.length) await this.delay(1100);
    }

    this.zone.run(() => {
      this.geocoding = false;
      this.applyFiltersNoRemap();
      this.cdr.markForCheck();
    });
  }

  private geocodeKey(p: Property): string {
    const locality = (p['Locality'] || p['Village/City/Town'] || '').trim();
    const district = (p['District'] || '').trim();
    const pin      = (p['Pin Code'] || '').trim();
    return `${locality}|${district}|${pin}`;
  }

  private async geocodeProperty(p: Property): Promise<MappedProperty | null> {
    if (p.lat && p.lng) {
      // Already has coords — store in cache so we don't re-check next time
      const key = this.geocodeKey(p);
      this.mapCache.setGeocode(key, { lat: p.lat, lng: p.lng });
      return { ...p, lat: p.lat, lng: p.lng, _geocoded: true };
    }

    const key      = this.geocodeKey(p);
    const street   = (p['Street']    || '').trim();
    const landmark = (p['Land mark'] || '').trim();
    const locality = (p['Locality']  || p['Village/City/Town'] || '').trim();
    const district = (p['District']  || '').trim();
    const pin      = (p['Pin Code']  || '').trim();

    try {
      const coords = await this.nominatimGeocode(street, landmark, locality, district, pin);
      this.mapCache.setGeocode(key, coords);   // persists to localStorage
      if (!coords) return null;
      return { ...p, lat: coords.lat, lng: coords.lng, _geocoded: true };
    } catch {
      this.mapCache.setGeocode(key, null);
      return null;
    }
  }

  private async nominatimGeocode(
    street: string, landmark: string,
    locality: string, district: string, pin: string
  ): Promise<{ lat: number; lng: number } | null> {
    // POST to our own backend proxy — avoids CORS + respects Nominatim rate limit server-side
    try {
      const resp = await fetch(`${environment.apiUrl}/geocode`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ street, landmark, locality, district, pinCode: pin })
      });
      if (resp.status === 404) return null;   // geocode not found
      if (!resp.ok) return null;
      const data = await resp.json();
      if (data?.lat && data?.lng) {
        return { lat: data.lat, lng: data.lng };
      }
    } catch { /* network error — return null so geocoding continues */ }
    return null;
  }

  // ── Filtering ─────────────────────────────────────────────────────────
  applyFilters(): void {
    this.applyFiltersNoRemap();
    if (this.mapReady) this.renderMarkers();
    this.cdr.markForCheck();
  }

  onSearchChange(val: string): void {
    this.searchQuery = val;
    this.searchSubject.next(val);
  }

  clearFilters(): void {
    this.searchQuery = this.selectedDistrict = this.selectedStatus = this.selectedType = '';
    this.sortBy = 'name';
    this.applyFilters();
  }

  get hasActiveFilters(): boolean {
    return !!(this.searchQuery || this.selectedDistrict || this.selectedStatus || this.selectedType);
  }

  // ── Markers ───────────────────────────────────────────────────────────
  private getPinColor(status: string): string {
    const s = (status || '').toLowerCase();
    if (s.includes('complet'))                            return PIN_COLORS['completed'];
    if (s.includes('progress') || s.includes('ongoing')) return PIN_COLORS['ongoing'];
    if (s.includes('new'))                               return PIN_COLORS['new'];
    return PIN_COLORS['default'];
  }

  private clearMarkers(): void {
    this.markers.forEach(m => m.remove());
    this.markers = [];
  }

  /** Add a single marker to the map without clearing existing ones */
  private addMarker(p: MappedProperty): void {
    if (!this.matchesFilters(p)) return;

    if (!this.map || !this.mapReady) {
      // Map not ready yet — queue for flushing on map load
      this.markerQueue.push(p);
      return;
    }

    this.placeMarkerOnMap(p);
  }

  /** Actually create the DOM element and add to the live map */
  private placeMarkerOnMap(p: MappedProperty): void {
    const color  = this.getPinColor(p['Project Status'] || '');
    const name   = p['Project Name'] || '?';
    const svgStr = buildPinSvg(color, name);
    const blob   = new Blob([svgStr], { type: 'image/svg+xml' });
    const objUrl = URL.createObjectURL(blob);

    const img = new Image(36, 48);
    img.src = objUrl;
    img.onload = () => URL.revokeObjectURL(objUrl);

    const el = document.createElement('div');
    el.className    = 'map-marker';
    el.style.width  = '36px';
    el.style.height = '48px';
    el.style.cursor = 'pointer';
    el.appendChild(img);

    el.addEventListener('click',   (e) => { e.stopPropagation(); this.zone.run(() => this.selectProperty(p)); });
    el.addEventListener('dblclick',(e) => { e.stopPropagation(); this.zone.run(() => this.router.navigate(['/property', p.id])); });

    const marker = new maplibregl.Marker({ element: el, anchor: 'bottom' })
      .setLngLat([p.lng, p.lat])
      .addTo(this.map);

    p._marker = marker;
    this.markers.push(marker);
  }

  /** Drain the queue — called once the map fires 'load' */
  private flushMarkerQueue(): void {
    if (this.markerQueue.length === 0) return;

    const queued = [...this.markerQueue];
    this.markerQueue = [];
    const bounds = new maplibregl.LngLatBounds();

    queued.forEach(p => {
      this.placeMarkerOnMap(p);
      bounds.extend([p.lng, p.lat]);
    });

    if (!bounds.isEmpty()) {
      this.map.fitBounds(bounds, {
        padding: { top: 80, bottom: 80, left: 40, right: 60 },
        maxZoom: 14, duration: 900
      });
    }
  }

  /** Full re-render — used when filters change */
  private renderMarkers(): void {
    if (!this.map || !this.mapReady) return;
    this.clearMarkers();
    this.markerQueue = [];   // discard stale queue — full render covers everything
    this.closePopup();

    const bounds = new maplibregl.LngLatBounds();

    this.filteredProperties.forEach(p => {
      this.placeMarkerOnMap(p);
      bounds.extend([p.lng, p.lat]);
    });

    if (this.filteredProperties.length > 0 && !bounds.isEmpty()) {
      this.map.fitBounds(bounds, {
        padding: { top: 80, bottom: 80, left: 40, right: 60 },
        maxZoom: 14, duration: 900
      });
    }
  }

  /** Check if a property passes current filters without touching the map */
  private matchesFilters(p: MappedProperty): boolean {
    const q = this.searchQuery.toLowerCase().trim();
    if (q && !(
      (p['Project Name']      || '').toLowerCase().includes(q) ||
      (p['Locality']          || '').toLowerCase().includes(q) ||
      (p['District']          || '').toLowerCase().includes(q) ||
      (p['Village/City/Town'] || '').toLowerCase().includes(q) ||
      (p['Mandal']            || '').toLowerCase().includes(q) ||
      (p['Pin Code']          || '').toLowerCase().includes(q)
    )) return false;
    if (this.selectedDistrict && p['District']       !== this.selectedDistrict) return false;
    if (this.selectedStatus   && p['Project Status'] !== this.selectedStatus)   return false;
    if (this.selectedType     && p['Project Type']   !== this.selectedType)     return false;
    return true;
  }

  /** Update sidebar list only — does NOT touch map markers */
  private applyFiltersNoRemap(): void {
    this.filteredProperties = this.mappedProperties
      .filter(p => this.matchesFilters(p))
      .sort((a, b) => {
        if (this.sortBy === 'name')     return (a['Project Name']    || '').localeCompare(b['Project Name']    || '');
        if (this.sortBy === 'district') return (a['District']        || '').localeCompare(b['District']        || '');
        if (this.sortBy === 'status')   return (a['Project Status']  || '').localeCompare(b['Project Status']  || '');
        return 0;
      });
  }

  // ── Selection + Popup ─────────────────────────────────────────────────
  selectProperty(p: MappedProperty): void {
    // Deselect all markers visually
    this.markers.forEach(m => {
      const el = m.getElement();
      el?.classList.remove('marker-active');
    });

    this.selectedProperty = p;

    // Highlight this marker
    if (p._marker) {
      p._marker.getElement()?.classList.add('marker-active');
    }

    // Fly to with offset for popup
    this.map.flyTo({
      center: [p.lng, p.lat],
      zoom: Math.max(this.map.getZoom(), 14),
      speed: 1.4,
      curve: 1.2,
      offset: [0, -80]
    });

    // Show native Mapbox popup
    this.showMapboxPopup(p);
    this.cdr.markForCheck();
  }

  private showMapboxPopup(p: MappedProperty): void {
    this.closePopup();

    const status   = p['Project Status'] || 'Unknown';
    const type     = p['Project Type']   || '';
    const locality = p['Locality'] || p['Village/City/Town'] || p['Mandal'] || '';
    const district = p['District'] || '';
    const area     = p['Total Area(In sqmts)'] || '';
    const pin      = p['Pin Code'] || '';
    const approved = p['Approved Date'] || '';
    const color    = this.getPinColor(status);
    const detailUrl = `/property/${encodeURIComponent(p.id || '')}`;
    const waMsg     = encodeURIComponent(
      `Hi, I'm interested in ${p['Project Name'] || 'a property'} in ${locality || district}. Please share more details.`
    );
    const waUrl     = `https://wa.me/918977367700?text=${waMsg}`;
    const mapsUrl   = `https://www.google.com/maps/search/?api=1&query=${p.lat},${p.lng}`;
    const statusCls = this.getStatusClass(status);

    const html = `
    <div class="mp-popup">
      <!-- Header -->
      <div class="mp-popup-header">
        <div class="mp-popup-avatar" style="background:${color}">
          ${(p['Project Name'] || '?')[0].toUpperCase()}
        </div>
        <div class="mp-popup-title-block">
          <div class="mp-popup-name">${this.escHtml(p['Project Name'] || 'Unnamed Project')}</div>
          <div class="mp-popup-loc">
            <svg viewBox="0 0 24 24" width="10" height="10" fill="${color}" style="flex-shrink:0">
              <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z"/>
            </svg>
            ${this.escHtml(locality)}${district && locality ? ', ' : ''}${this.escHtml(district)}
          </div>
        </div>
      </div>

      <!-- Badges -->
      <div class="mp-popup-badges">
        <span class="mp-badge mp-badge-status ${statusCls}">${this.escHtml(status)}</span>
        ${type ? `<span class="mp-badge mp-badge-type">${this.escHtml(type)}</span>` : ''}
      </div>

      <!-- Key facts grid -->
      <div class="mp-popup-grid">
        ${area     ? `<div class="mp-popup-kv"><span class="mp-kv-label">Area</span><span class="mp-kv-val">${this.escHtml(area)} sqm</span></div>` : ''}
        ${pin      ? `<div class="mp-popup-kv"><span class="mp-kv-label">PIN</span><span class="mp-kv-val">${this.escHtml(pin)}</span></div>` : ''}
        ${approved ? `<div class="mp-popup-kv"><span class="mp-kv-label">Approved</span><span class="mp-kv-val">${this.escHtml(approved)}</span></div>` : ''}
      </div>

      <!-- Divider -->
      <div class="mp-divider"></div>

      <!-- Enquiry mini-form -->
      <div class="mp-enquiry">
        <div class="mp-enquiry-title">
          <svg viewBox="0 0 24 24" fill="currentColor" width="13" height="13"><path d="M20 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4l-8 5-8-5V6l8 5 8-5v2z"/></svg>
          Quick Enquiry
        </div>
        <div class="mp-form-row">
          <input id="mp-enq-name-${p.id}" type="text" class="mp-input" placeholder="Your name" autocomplete="name" />
          <input id="mp-enq-phone-${p.id}" type="tel" class="mp-input" placeholder="Mobile number" autocomplete="tel" maxlength="10" />
        </div>
        <button class="mp-enq-submit" id="mp-enq-submit-${p.id}" onclick="window.__mpEnquiry && window.__mpEnquiry('${p.id}')">
          Send Enquiry
        </button>
      </div>

      <!-- Divider -->
      <div class="mp-divider"></div>

      <!-- Action buttons -->
      <div class="mp-popup-actions">
        <a href="${detailUrl}" class="mp-popup-btn mp-popup-btn-primary" target="_self">
          <svg viewBox="0 0 24 24" width="13" height="13" fill="currentColor"><path d="M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5c-1.73-4.39-6-7.5-11-7.5zM12 17c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5zm0-8c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3z"/></svg>
          View Details
        </a>
        <button onclick="window.__mpVisit && window.__mpVisit('${this.escHtml(p.id||'')}','${this.escHtml(p['Project Name']||'')}')"
                class="mp-popup-btn mp-popup-btn-visit">
          <svg viewBox="0 0 24 24" width="13" height="13" fill="currentColor"><path d="M17 12h-5v5h5v-5zM16 1v2H8V1H6v2H5c-1.11 0-1.99.9-1.99 2L3 19c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2h-1V1h-2zm3 18H5V8h14v11z"/></svg>
          Visit
        </button>
        <a href="${waUrl}" target="_blank" rel="noopener" class="mp-popup-btn mp-popup-btn-wa">
          <svg viewBox="0 0 32 32" fill="currentColor" width="14" height="14"><path d="M16 0C7.163 0 0 7.163 0 16c0 2.822.736 5.469 2.027 7.77L0 32l8.454-2.007A15.938 15.938 0 0016 32c8.837 0 16-7.163 16-16S24.837 0 16 0zm8.006 22.394c-.34.957-1.99 1.826-2.738 1.942-.72.113-1.624.161-2.619-.165-1.609-.52-3.748-2.126-5.233-3.59C11.93 19.12 10.3 17.02 9.74 15.43c-.557-1.587-.128-2.888.217-3.568.347-.682.778-.86 1.039-.882.261-.022.522-.027.752-.018.239.01.56-.09.875.671.32.778 1.083 2.664 1.179 2.857.097.192.16.417.032.672-.127.255-.19.414-.38.638-.188.224-.396.5-.565.672-.188.19-.384.396-.165.776.219.38.975 1.608 2.095 2.605 1.434 1.276 2.644 1.67 3.022 1.857.377.188.598.16.822-.096.224-.255.957-1.12 1.213-1.503.255-.384.51-.32.86-.192.35.128 2.22 1.048 2.6 1.238.38.19.634.286.728.446.094.16.094.926-.246 1.882z"/></svg>
          WhatsApp
        </a>
      </div>
    </div>`;

    // Register global enquiry handler
    (window as any).__mpEnquiry = async (propId: string) => {
      const nameEl  = document.getElementById(`mp-enq-name-${propId}`)  as HTMLInputElement;
      const phoneEl = document.getElementById(`mp-enq-phone-${propId}`) as HTMLInputElement;
      const submitBtn = document.querySelector(`#mp-enq-submit-${propId}`) as HTMLButtonElement;
      const name    = nameEl?.value?.trim()  || '';
      const phone   = phoneEl?.value?.trim() || '';

      // Inline validation
      nameEl?.classList.toggle('mp-input-error', !name);
      phoneEl?.classList.toggle('mp-input-error', !phone || !/^\d{10}$/.test(phone));
      if (!name || !/^\d{10}$/.test(phone)) return;

      // Disable button while submitting
      if (submitBtn) { submitBtn.disabled = true; submitBtn.textContent = 'Sending…'; }

      try {
        const resp = await fetch('/api/submit_lead', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            name,
            email:           `${phone}@noemail.hydurban.in`,  // placeholder when no email provided
            mobile:          phone,
            areaOfInterest:  p['Locality'] || p['District'] || 'Hyderabad',
            projectName:     p['Project Name'] || '',
            projectId:       p.id || '',
            source:          'map_popup'
          })
        });

        if (resp.ok) {
          // Success — show thank-you state in the popup
          const form = nameEl?.closest('.mp-enquiry') as HTMLElement;
          if (form) {
            form.innerHTML = `
              <div style="text-align:center;padding:10px 0;">
                <div style="color:#10b981;font-size:20px;margin-bottom:6px;">✓</div>
                <div style="font-size:12px;font-weight:700;color:#1e293b;">Enquiry sent!</div>
                <div style="font-size:11px;color:#64748b;margin-top:3px;">We'll call you within 24 hours.</div>
              </div>`;
          }
        } else {
          // Restore button on failure
          if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = 'Send Enquiry'; }
          phoneEl?.classList.add('mp-input-error');
        }
      } catch {
        if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = 'Send Enquiry'; }
      }
    };

    // Register global visit handler — bridges the Mapbox popup DOM to Angular
    (window as any).__mpVisit = (propId: string, propName: string) => {
      this.zone.run(() => this.openVisitModal(propName, propId));
    };

    this.activePopup = new maplibregl.Popup({
      closeButton: true,
      closeOnClick: false,
      maxWidth: '340px',
      offset: 52,
      className: 'mapbox-custom-popup'
    })
      .setLngLat([p.lng, p.lat])
      .setHTML(html)
      .addTo(this.map);

    this.activePopup.on('close', () => {
      this.zone.run(() => {
        this.selectedProperty = null;
        this.markers.forEach(m => m.getElement()?.classList.remove('marker-active'));
        this.cdr.markForCheck();
      });
    });
  }

  private escHtml(str: string): string {
    return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  openVisitModal(propName: string, propId: string): void {
    this.visitProjectName = propName;
    this.visitProjectId   = propId;
    this.showVisitModal   = true;
    this.closePopup();
    this.cdr.markForCheck();
  }

  private closePopup(): void {
    if (this.activePopup) {
      this.activePopup.remove();
      this.activePopup = null;
    }
  }

  // ── Navigation helpers ────────────────────────────────────────────────
  navigateToDetail(p: MappedProperty): void {
    this.router.navigate(['/property', p.id]);
  }

  flyToAll(): void {
    if (!this.map || this.filteredProperties.length === 0) return;
    const bounds = new maplibregl.LngLatBounds();
    this.filteredProperties.forEach(p => bounds.extend([p.lng, p.lat]));
    this.map.fitBounds(bounds, {
      padding: { top: 80, bottom: 80, left: 40, right: 60 },
      maxZoom: 14,
      duration: 900
    });
  }

  flyToProperty(p: MappedProperty, event: Event): void {
    event.stopPropagation();
    this.selectProperty(p);
    // Scroll sidebar card into view
    setTimeout(() => {
      document.getElementById(`prop-${p.id}`)?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }, 100);
  }

  toggleSidebar(): void {
    this.sidebarOpen = !this.sidebarOpen;
    setTimeout(() => { if (this.map) this.map.resize(); }, 320);
  }

  // ── Helpers ────────────────────────────────────────────────────────────
  getProjectInitial(p: Property): string {
    return (p['Project Name'] || '?')[0].toUpperCase();
  }

  getStatusClass(status: string | undefined): string {
    const s = (status || '').toLowerCase();
    if (s.includes('complet'))                          return 'status-completed';
    if (s.includes('progress') || s.includes('ongoing')) return 'status-ongoing';
    if (s.includes('new'))                              return 'status-new';
    return 'status-default';
  }

  getAvatarClass(p: Property): string {
    return 'avatar-' + (this.getProjectInitial(p).charCodeAt(0) % 6);
  }

  getStatusColor(status: string | undefined): string {
    return this.getPinColor(status || '');
  }

  trackById(_: number, p: Property): string {
    return p.id || '';
  }

  get progressPercent(): number {
    return this.geocodingTotal ? Math.round((this.geocodingProgress / this.geocodingTotal) * 100) : 0;
  }

  private delay(ms: number): Promise<void> {
    return new Promise(r => setTimeout(r, ms));
  }
}
