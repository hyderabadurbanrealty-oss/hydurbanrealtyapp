import { Injectable } from '@angular/core';
import { Observable, of, from, Subject } from 'rxjs';
import { tap, share, switchMap } from 'rxjs/operators';
import { PropertyService } from './property.service';
import { Property } from '../map/map.component';

// ── Constants ──────────────────────────────────────────────────────────────
const DB_NAME          = 'hyu_map_cache';
const DB_VERSION       = 2;
const STORE_PROPERTIES = 'properties';
const STORE_GEOCODES   = 'geocodes';

const PROPERTY_TTL  = 60 * 60 * 1000;           // 1 hour
const GEOCODE_TTL   = 7 * 24 * 60 * 60 * 1000;  // 7 days

interface IDBRecord<T> { key: string; data: T; ts: number; }

// ══════════════════════════════════════════════════════════════════════════
// Thin IndexedDB wrapper — no external packages
// ══════════════════════════════════════════════════════════════════════════
class IdbStore {
  private _db: IDBDatabase | null = null;
  private _ready: Promise<IDBDatabase>;

  constructor() {
    this._ready = this._open();
  }

  private _open(): Promise<IDBDatabase> {
    return new Promise((resolve, reject) => {
      if (typeof indexedDB === 'undefined') {
        reject(new Error('IndexedDB not available'));
        return;
      }

      const req = indexedDB.open(DB_NAME, DB_VERSION);

      req.onupgradeneeded = (e) => {
        const db = (e.target as IDBOpenDBRequest).result;

        // Properties store — keyed by a single 'all' entry
        if (!db.objectStoreNames.contains(STORE_PROPERTIES)) {
          db.createObjectStore(STORE_PROPERTIES, { keyPath: 'key' });
        }

        // Geocodes store — keyed by locality|district|pin
        if (!db.objectStoreNames.contains(STORE_GEOCODES)) {
          const gs = db.createObjectStore(STORE_GEOCODES, { keyPath: 'key' });
          gs.createIndex('ts', 'ts');   // index for TTL pruning
        }
      };

      req.onsuccess  = (e) => { this._db = (e.target as IDBOpenDBRequest).result; resolve(this._db); };
      req.onerror    = () => reject(req.error);
      req.onblocked  = () => reject(new Error('IDB blocked — close other tabs'));
    });
  }

  async get<T>(store: string, key: string): Promise<IDBRecord<T> | undefined> {
    const db = await this._ready;
    return new Promise((resolve, reject) => {
      const tx  = db.transaction(store, 'readonly');
      const req = tx.objectStore(store).get(key);
      req.onsuccess = () => resolve(req.result as IDBRecord<T> | undefined);
      req.onerror   = () => reject(req.error);
    });
  }

  async set<T>(store: string, key: string, data: T): Promise<void> {
    const db = await this._ready;
    return new Promise((resolve, reject) => {
      const tx  = db.transaction(store, 'readwrite');
      const req = tx.objectStore(store).put({ key, data, ts: Date.now() } as IDBRecord<T>);
      req.onsuccess = () => resolve();
      req.onerror   = () => reject(req.error);
    });
  }

  async delete(store: string, key: string): Promise<void> {
    const db = await this._ready;
    return new Promise((resolve, reject) => {
      const tx  = db.transaction(store, 'readwrite');
      const req = tx.objectStore(store).delete(key);
      req.onsuccess = () => resolve();
      req.onerror   = () => reject(req.error);
    });
  }

  /** Read all entries from a store */
  async getAll<T>(store: string): Promise<IDBRecord<T>[]> {
    const db = await this._ready;
    return new Promise((resolve, reject) => {
      const tx  = db.transaction(store, 'readonly');
      const req = tx.objectStore(store).getAll();
      req.onsuccess = () => resolve(req.result as IDBRecord<T>[]);
      req.onerror   = () => reject(req.error);
    });
  }

  /** Batch-write geocodes efficiently in a single transaction */
  async putMany<T>(store: string, entries: { key: string; data: T }[]): Promise<void> {
    if (!entries.length) return;
    const db = await this._ready;
    return new Promise((resolve, reject) => {
      const tx = db.transaction(store, 'readwrite');
      const os = tx.objectStore(store);
      const ts = Date.now();
      entries.forEach(e => os.put({ key: e.key, data: e.data, ts } as any));
      tx.oncomplete = () => resolve();
      tx.onerror    = () => reject(tx.error);
    });
  }

  /** Delete all entries older than ttlMs */
  async pruneOlderThan(store: string, ttlMs: number): Promise<number> {
    const db  = await this._ready;
    const cutoff = Date.now() - ttlMs;
    return new Promise((resolve, reject) => {
      const tx  = db.transaction(store, 'readwrite');
      const os  = tx.objectStore(store);
      const req = os.openCursor();
      let pruned = 0;
      req.onsuccess = (e) => {
        const cursor = (e.target as IDBRequest<IDBCursorWithValue>).result;
        if (!cursor) { resolve(pruned); return; }
        if ((cursor.value as IDBRecord<any>).ts < cutoff) {
          cursor.delete();
          pruned++;
        }
        cursor.continue();
      };
      req.onerror = () => reject(req.error);
    });
  }
}

// ══════════════════════════════════════════════════════════════════════════
// MapCacheService
// ══════════════════════════════════════════════════════════════════════════
@Injectable({ providedIn: 'root' })
export class MapCacheService {

  private idb = new IdbStore();

  // ── In-memory hot layer (avoids IDB round-trip on same-session navigations) ──
  private _memProps:  Property[] | null = null;
  private _memPropTs = 0;
  private _inflight$: Observable<Property[]> | null = null;
  private _bootDone: Promise<void>;  // resolves when IDB boot is complete

  // Geocode write queue — batch-flush every 2 seconds
  private _geoQueue: { key: string; data: { lat: number; lng: number } | null }[] = [];
  private _geoFlushTimer: any = null;

  // In-memory geocode map for this session (fast lookup, backed by IDB)
  private _geoMem = new Map<string, { lat: number; lng: number } | null>();
  private _geoLoaded = false;

  constructor(private svc: PropertyService) {
    this._bootDone = this._bootProperties();  // store the promise
    this._bootGeocodes();
  }

  // ════════════════════════════════════════════════════════════════════════
  // Property list
  // ════════════════════════════════════════════════════════════════════════

  getProperties(): Observable<Property[]> {
    const now = Date.now();

    // 1. Hot in-memory — instant (only valid after boot completes)
    if (this._memProps && (now - this._memPropTs) < PROPERTY_TTL) {
      return of(this._memProps);
    }

    // 2. Share any in-flight fetch
    if (this._inflight$) return this._inflight$;

    // 3. Wait for IDB boot to finish, then decide: IDB hit or API call
    this._inflight$ = from(this._bootDone).pipe(
      switchMap(() => {
        // Boot completed — check memory again (boot may have populated it)
        if (this._memProps && (Date.now() - this._memPropTs) < PROPERTY_TTL) {
          return of(this._memProps);
        }
        // IDB was empty/expired — fetch from API
        return this.svc.getProperties().pipe(
          tap(props => {
            this._setMemProperties(props);
            this._savePropertiesToIdb(props);
          })
        );
      }),
      tap(() => { this._inflight$ = null; }),
      share()
    );

    return this._inflight$;
  }

  private _setMemProperties(props: Property[]): void {
    this._memProps  = props;
    this._memPropTs = Date.now();
  }

  private async _bootProperties(): Promise<void> {
    try {
      const cached = await this._loadPropertiesFromIdb();
      if (cached) {
        this._setMemProperties(cached);
        console.debug(`[MapCache] Loaded ${cached.length} properties from IDB`);
      }
    } catch {
      // IDB unavailable — getProperties() will fall through to API
    }
  }

  private async _loadPropertiesFromIdb(): Promise<Property[] | null> {
    try {
      const rec = await this.idb.get<Property[]>(STORE_PROPERTIES, 'all');
      if (!rec) return null;
      if (Date.now() - rec.ts > PROPERTY_TTL) {
        // Expired — delete and return null so API is fetched
        await this.idb.delete(STORE_PROPERTIES, 'all');
        return null;
      }
      return rec.data;
    } catch { return null; }
  }

  private _savePropertiesToIdb(props: Property[]): void {
    this.idb.set(STORE_PROPERTIES, 'all', props).catch(() => {
      // IDB write failed (e.g. private mode) — in-memory still works
    });
  }

  invalidateProperties(): void {
    this._memProps  = null;
    this._memPropTs = 0;
    this._inflight$ = null;
    this.idb.delete(STORE_PROPERTIES, 'all').catch(() => {});
  }

  // ════════════════════════════════════════════════════════════════════════
  // Geocode cache
  // ════════════════════════════════════════════════════════════════════════

  private async _bootGeocodes(): Promise<void> {
    try {
      const pruned = await this.idb.pruneOlderThan(STORE_GEOCODES, GEOCODE_TTL);
      if (pruned > 0) console.debug(`[MapCache] Pruned ${pruned} expired geocode entries`);

      const all = await this.idb.getAll<{ lat: number; lng: number } | null>(STORE_GEOCODES);
      all.forEach(rec => this._geoMem.set(rec.key, rec.data));
      this._geoLoaded = true;
      console.debug(`[MapCache] Loaded ${all.length} geocodes from IDB`);
    } catch {
      this._geoLoaded = true; // mark ready even if IDB failed
    }
  }

  hasGeocode(key: string): boolean {
    return this._geoMem.has(key);
  }

  getGeocode(key: string): { lat: number; lng: number } | null | undefined {
    return this._geoMem.get(key);
  }

  setGeocode(key: string, coords: { lat: number; lng: number } | null): void {
    this._geoMem.set(key, coords);
    // Only persist successful geocodes (null = failed, don't waste IDB space)
    if (coords !== null) {
      this._geoQueue.push({ key, data: coords });
      this._scheduleGeoFlush();
    }
  }

  get geocodeCacheSize(): number { return this._geoMem.size; }

  private _scheduleGeoFlush(): void {
    if (this._geoFlushTimer) return;
    this._geoFlushTimer = setTimeout(() => {
      this._geoFlushTimer = null;
      const batch = [...this._geoQueue];
      this._geoQueue = [];
      if (batch.length) {
        this.idb.putMany(STORE_GEOCODES, batch).catch(() => {});
      }
    }, 2000);
  }

  // ════════════════════════════════════════════════════════════════════════
  // Diagnostics / maintenance
  // ════════════════════════════════════════════════════════════════════════

  clearAll(): void {
    this.invalidateProperties();
    this._geoMem.clear();
    this.idb.delete(STORE_GEOCODES, 'all').catch(() => {});
    // Nuke geocodes store entirely
    indexedDB.deleteDatabase(DB_NAME);
  }

  /** Returns a summary of what's cached — useful for debug/admin. */
  async getCacheStats(): Promise<{ properties: boolean; geocodes: number; propAge: string }> {
    const propRec = await this.idb.get<Property[]>(STORE_PROPERTIES, 'all').catch(() => undefined);
    const geoRecs = await this.idb.getAll(STORE_GEOCODES).catch(() => [] as any[]);
    const ageMs   = propRec ? Date.now() - propRec.ts : -1;
    const ageStr  = ageMs < 0 ? 'none' : ageMs < 60000 ? `${Math.round(ageMs/1000)}s ago`
                  : ageMs < 3600000 ? `${Math.round(ageMs/60000)}m ago`
                  : `${Math.round(ageMs/3600000)}h ago`;
    return {
      properties: !!propRec,
      geocodes:   geoRecs.length,
      propAge:    ageStr
    };
  }
}
