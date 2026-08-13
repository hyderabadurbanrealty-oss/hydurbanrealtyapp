import { Component } from '@angular/core';
import { FormBuilder, FormGroup, Validators, AbstractControl, ValidationErrors } from '@angular/forms';
import { Router, ActivatedRoute } from '@angular/router';
import { AuthService } from '../services/auth.service';

function passwordMatchValidator(g: AbstractControl): ValidationErrors | null {
  const pass = g.get('password')?.value;
  const confirm = g.get('confirmPassword')?.value;
  return pass === confirm ? null : { passwordMismatch: true };
}

@Component({
  selector: 'app-register',
  templateUrl: './register.component.html',
  styleUrls: ['./register.component.css']
})
export class RegisterComponent {
  form: FormGroup;
  loading = false;
  success = false;
  error = '';
  showPassword = false;

  constructor(
    private fb: FormBuilder,
    private auth: AuthService,
    private router: Router
  ) {
    this.form = this.fb.group({
      fullName: ['', [Validators.required, Validators.minLength(2)]],
      email: ['', [Validators.required, Validators.email]],
      password: ['', [Validators.required, Validators.minLength(8)]],
      confirmPassword: ['', Validators.required],
      mobile: ['', [Validators.pattern(/^[6-9]\d{9}$/)]]
    }, { validators: passwordMatchValidator });
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
