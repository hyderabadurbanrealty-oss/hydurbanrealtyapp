import { Injectable } from '@angular/core';
import { BehaviorSubject } from 'rxjs';
import { Property } from '../map/map.component';

export const COMPARE_MAX = 3;

@Injectable({ providedIn: 'root' })
export class CompareService {
  private _list = new BehaviorSubject<Property[]>([]);
  list$ = this._list.asObservable();

  get list(): Property[] { return this._list.getValue(); }

  isInList(id: string): boolean {
    return this.list.some(p => this.getId(p) === id);
  }

  canAdd(): boolean { return this.list.length < COMPARE_MAX; }

  add(property: Property): boolean {
    const id = this.getId(property);
    if (!id || this.isInList(id) || !this.canAdd()) return false;
    this._list.next([...this.list, property]);
    return true;
  }

  remove(id: string): void {
    this._list.next(this.list.filter(p => this.getId(p) !== id));
  }

  clear(): void { this._list.next([]); }

  private getId(p: Property): string {
    return (p as any).id ?? (p as any).projectId ?? '';
  }
}
