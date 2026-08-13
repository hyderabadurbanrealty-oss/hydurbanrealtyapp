import { Component, OnInit } from '@angular/core';
import { FormBuilder, FormGroup, Validators } from '@angular/forms';
import { Router, ActivatedRoute } from '@angular/router';
import { AuthService } from './services/auth.service';

@Component({
  selector: 'app-login',
  templateUrl: './login.component.html',
  styleUrls: ['./login.component.css']
})
export class LoginComponent implements OnInit {
  form: FormGroup;
  loading = false;
  error = '';
  showPassword = false;
  private returnUrl = '/';

  constructor(
    private fb: FormBuilder,
    private auth: AuthService,
    private router: Router,
    private route: ActivatedRoute
  ) {
    this.form = this.fb.group({
      email: ['', [Validators.required, Validators.email]],
      password: ['', Validators.required]
    });
  }

  ngOnInit(): void {
    // Already logged in? Redirect away
    if (this.auth.isLoggedIn()) {
      this.router.navigate(['/']);
      return;
    }
    this.returnUrl = this.route.snapshot.queryParamMap.get('returnUrl') || '/';
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
        // Admin goes to /admin, everyone else to returnUrl or home
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
