import { Component, OnInit } from '@angular/core';
import { FormBuilder, FormGroup, Validators, AbstractControl, ValidationErrors } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { AuthService } from '../services/auth.service';

function passwordMatchValidator(g: AbstractControl): ValidationErrors | null {
  return g.get('newPassword')?.value === g.get('confirmPassword')?.value
    ? null : { passwordMismatch: true };
}

@Component({
  selector: 'app-reset-password',
  templateUrl: './reset-password.component.html',
  styleUrls: ['./reset-password.component.css']
})
export class ResetPasswordComponent implements OnInit {
  form: FormGroup;
  loading = false;
  success = false;
  error = '';
  tokenMissing = false;
  private token = '';

  showNew     = false;
  showConfirm = false;

  get pwStrength(): number {
    const v: string = this.form.get('newPassword')?.value || '';
    if (!v) return 0;
    let score = 0;
    if (v.length >= 8)  score++;
    if (v.length >= 12) score++;
    if (/[A-Z]/.test(v) && /[a-z]/.test(v)) score++;
    if (/[0-9]/.test(v) || /[^A-Za-z0-9]/.test(v)) score++;
    return score;
  }

  get pwStrengthLabel(): string {
    return ['', 'Weak', 'Fair', 'Good', 'Strong'][this.pwStrength] || '';
  }

  get pwStrengthClass(): string {
    return ['', 'weak', 'fair', 'good', 'strong'][this.pwStrength] || '';
  }

  constructor(
    private fb: FormBuilder,
    private auth: AuthService,
    private route: ActivatedRoute,
    private router: Router
  ) {
    this.form = this.fb.group({
      newPassword: ['', [Validators.required, Validators.minLength(8)]],
      confirmPassword: ['', Validators.required]
    }, { validators: passwordMatchValidator });
  }

  ngOnInit(): void {
    this.token = this.route.snapshot.queryParamMap.get('token') || '';
    if (!this.token) this.tokenMissing = true;
  }

  get f() { return this.form.controls; }

  submit(): void {
    if (this.form.invalid) { this.form.markAllAsTouched(); return; }
    this.loading = true;
    this.error = '';
    this.auth.resetPassword(this.token, this.form.value.newPassword).subscribe({
      next: () => { this.loading = false; this.success = true; },
      error: err => {
        this.loading = false;
        const code = err.error?.error;
        this.error = code === 'token_invalid'
          ? 'This reset link has expired or already been used. Please request a new one.'
          : err.error?.message || 'Reset failed. Please try again.';
      }
    });
  }
}
