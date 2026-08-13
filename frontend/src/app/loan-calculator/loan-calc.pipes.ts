import { Pipe, PipeTransform } from '@angular/core';

interface CmpResult { emi: number; totalInterest: number; }

@Pipe({ name: 'minEmi' })
export class MinEmiPipe implements PipeTransform {
  transform(results: CmpResult[]): number {
    return results.length ? Math.min(...results.map(r => r.emi)) : 0;
  }
}

@Pipe({ name: 'maxEmi' })
export class MaxEmiPipe implements PipeTransform {
  transform(results: CmpResult[]): number {
    return results.length ? Math.max(...results.map(r => r.emi)) : 0;
  }
}

@Pipe({ name: 'minTotalInt' })
export class MinTotalIntPipe implements PipeTransform {
  transform(results: CmpResult[]): number {
    return results.length ? Math.min(...results.map(r => r.totalInterest)) : 0;
  }
}
