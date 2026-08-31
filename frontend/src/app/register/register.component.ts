import { Component, OnInit, NgZone } from '@angular/core';
import { FormBuilder, FormGroup, Validators, AbstractControl, ValidationErrors } from '@angular/forms';
import { Router, ActivatedRoute } from '@angular/router';
import { AuthService } from '../services/auth.service';
import { environment } from '../../environments/environment';

declare const google: any;

function passwordMatchValidator(g: AbstractControl): ValidationErrors | null {
  const pass = g.get('password')?.value;
  const confirm = g.get('confirmPassword')?.value;
  return pass === confirm ? null : { passwordMismatch: true };
}

@Component({
  standalone: false,
  selector: 'app-register',
  templateUrl: './register.component.html',
  styleUrls: ['./register.component.css']
})
export class RegisterComponent implements OnInit {
  form: FormGroup;
  loading = false;
  googleLoading = false;
  success = false;
  error = '';
  showPassword = false;

  constructor(
    private fb: FormBuilder,
    private auth: AuthService,
    private router: Router,
    private zone: NgZone
  ) {
    this.form = this.fb.group({
      fullName: ['', [Validators.required, Validators.minLength(2)]],
      email: ['', [Validators.required, Validators.email]],
      password: ['', [Validators.required, Validators.minLength(8)]],
      confirmPassword: ['', Validators.required],
      mobile: ['', [Validators.pattern(/^[6-9]\d{9}$/)]]
    }, { validators: passwordMatchValidator });
  }

  ngOnInit(): void {
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
        document.getElementById('google-register-btn'),
        { theme: 'outline', size: 'large', width: '100%', text: 'signup_with', shape: 'rectangular' }
      );
    }, 400);
  }

  handleGoogleResponse(response: any): void {
    if (!response?.credential) { this.error = 'Google sign-in failed. Please try again.'; return; }
    this.googleLoading = true;
    this.error = '';
    this.auth.loginWithGoogle(response.credential).subscribe({
      next: () => { this.googleLoading = false; this.router.navigate(['/']); },
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
    const { fullName, email, password, mobile } = this.form.value;
    this.auth.register(fullName, email, password, mobile || undefined).subscribe({
      next: () => { this.loading = false; this.success = true; },
      error: err => {
        this.loading = false;
        const code = err.error?.error;
        this.error = code === 'email_already_exists'
          ? 'An account with this email already exists.'
          : err.error?.message || 'Registration failed. Please try again.';
      }
    });
  }
}
