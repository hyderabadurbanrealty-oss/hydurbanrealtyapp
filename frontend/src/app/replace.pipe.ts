import { Pipe, PipeTransform } from '@angular/core';

@Pipe({
  standalone: false,
  name: 'replace'
})
export class ReplacePipe implements PipeTransform {
  transform(value: string, find: string, replace: string): string {
    if (!value) return value;
    return value.replace(new RegExp(find, 'g'), replace);
  }
}
