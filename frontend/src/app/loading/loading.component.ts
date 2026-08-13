import { Component } from '@angular/core';
import { Observable } from 'rxjs';
import { LoadingService } from '../services/loading.service';

@Component({
  selector: 'app-loading',
  templateUrl: './loading.component.html',
  styleUrls: ['./loading.component.css']
})
export class LoadingComponent {
  isLoading$!: Observable<boolean>;
  isHiding$!: Observable<boolean>;

  constructor(private loadingService: LoadingService) {
    this.isLoading$ = this.loadingService.loading$;
    this.isHiding$ = this.loadingService.hiding$;
  }
}
