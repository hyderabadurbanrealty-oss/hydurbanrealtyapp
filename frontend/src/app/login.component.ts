import { Component, OnInit, NgZone } from '@angular/core';
import { FormBuilder, FormGroup, Validators } from '@angular/forms';
import { Router, ActivatedRoute } from '@angular/router';
import { AuthService } from './services/auth.service';
import { environment } from '../environments/environment';

declare const google: any;

@Component({
  standalone: false,
  selector: 'app-login',
  templateUrl: './login.component.html',
  styleUrls: ['./login.component.css']
})
export class LoginComponent implements OnInit {
  form: FormGroup;
  loading = false;
  googleLoading = false;
  error = '';
  showPassword = false;
  private returnUrl = '/';

  constructor(
    private fb: FormBuilder,
    private auth: AuthService,
    private router: Router,
    private route: ActivatedRoute,
    private zone: NgZone
  ) {
    this.form = this.fb.group({
      email: ['', [Validators.required, Validators.email]],
      password: ['', Validators.required]
    });
  }

  ngOnInit(): void {
    if (this.auth.isLoggedIn()) { this.router.navigate(['/']); return; }
    this.returnUrl = this.route.snapshot.queryParamMap.get('returnUrl') || '/';
    this.initGoogleSignIn();
  }

  private initGoogleSignIn(): void {
    setTimeout(() => {
      if (typeof google === 'undefined') return;
      google.accounts.id.initialize({
        client_id: environment.googleClientId,
        callback: (resp: any) => this.zone.run(() => this.handleGoogleResponse(resp))
      });
      google.accounts.id.renderButton(
        document.getElementById('google-signin-btn'),
        { theme: 'outline', size: 'large', width: '100%', text: 'signin_with', shape: 'rectangular' }
      );
    }, 400);
  }

  handleGoogleResponse(response: any): void {
    if (!response?.credential) { this.error = 'Google sign-in failed. Please try again.'; return; }
    this.googleLoading = true;
    this.error = '';
    this.auth.loginWithGoogle(response.credential).subscribe({
      next: resp => {
        this.googleLoading = false;
        const dest = resp.user.role === 'admin' ? '/admin' : this.returnUrl;
        this.router.navigate([dest]);
      },
      error: err => {
        this.googleLoading = false;
        this.error = err.error?.message || 'Google sign-in failed. Please try again.';
      }
    });
  }

  get f() { return this.form.controls; }

  submit(): void {
    if (this.form.invalid) { this.form.markAllAsTouched(); return; }
    this.loading = true;
    this.error = '';
    const { email, password } = this.form.value;
    this.auth.login(email, password).subscribe({
      next: resp => {
        this.loading = false;
        const dest = resp.user.role === 'admin' ? '/admin' : this.returnUrl;
        this.router.navigate([dest]);
      },
      error: err => {
        this.loading = false;
        const code = err.error?.error;
        this.error = code === 'invalid_credentials'
          ? 'Incorrect email or password.'
          : err.error?.message || 'Login failed. Please try again.';
      }
    });
  }
}
