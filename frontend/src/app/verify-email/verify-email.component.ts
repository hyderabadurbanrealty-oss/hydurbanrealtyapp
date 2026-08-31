import { Component, OnInit } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { AuthService } from '../services/auth.service';

@Component({
  standalone: false,
  selector: 'app-verify-email',
  templateUrl: './verify-email.component.html',
  styleUrls: ['./verify-email.component.css']
})
export class VerifyEmailComponent implements OnInit {
  status: 'loading' | 'success' | 'error' = 'loading';
  errorCode = '';

  constructor(private route: ActivatedRoute, private auth: AuthService, private router: Router) {}

  ngOnInit(): void {
    const token = this.route.snapshot.queryParamMap.get('token') || '';
    if (!token) { this.status = 'error'; this.errorCode = 'missing_token'; return; }

    this.auth.verifyEmail(token).subscribe({
      next: () => this.status = 'success',
      error: err => {
        this.status = 'error';
        this.errorCode = err.error?.error || 'unknown';
      }
    });
  }

  get errorMessage(): string {
    const m: Record<string, string> = {
      missing_token: 'No verification token found. Please use the link from your email.',
      token_expired: 'This verification link has expired. Please request a new one below.',
      token_already_used: 'This link has already been used. Your email may already be verified.',
      invalid_token: 'Invalid verification link. Please request a new one below.',
    };
    return m[this.errorCode] || 'Verification failed. Please try again.';
  }
}
