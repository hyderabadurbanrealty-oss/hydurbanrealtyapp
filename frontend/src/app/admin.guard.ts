import { Injectable } from '@angular/core';
import { CanActivate, Router } from '@angular/router';
import { AuthService } from './services/auth.service';

@Injectable({ providedIn: 'root' })
export class AdminGuard implements CanActivate {
  constructor(private auth: AuthService, private router: Router) {}

  canActivate(): boolean {
    // Check new JWT-based auth first, fall back to legacy isAdmin flag
    const user = this.auth.getCurrentUser();
    if (user?.role === 'admin') return true;
    if (!user && localStorage.getItem('isAdmin') === 'true' && this.auth.getAccessToken()) return true;
    this.router.navigate(['/login']);
    return false;
  }
}
