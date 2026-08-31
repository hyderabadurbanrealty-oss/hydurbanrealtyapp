import { Component, OnInit } from '@angular/core';
import { FormBuilder, FormGroup, Validators, AbstractControl, ValidationErrors } from '@angular/forms';
import { Router } from '@angular/router';
import { AuthService, UserProfile } from '../services/auth.service';

function passwordMatchValidator(g: AbstractControl): ValidationErrors | null {
  const np = g.get('newPassword')?.value;
  const cp = g.get('confirmPassword')?.value;
  return np === cp ? null : { passwordMismatch: true };
}

@Component({
  standalone: false,
  selector: 'app-user-profile',
  templateUrl: './user-profile.component.html',
  styleUrls: ['./user-profile.component.css']
})
export class UserProfileComponent implements OnInit {
  user: UserProfile | null = null;
  activeTab: 'profile' | 'security' = 'profile';

  profileForm!: FormGroup;
  pwForm!: FormGroup;

  profileLoading = false;
  profileSuccess = '';
  profileError = '';

  pwLoading = false;
  pwSuccess = '';
  pwError = '';

  deleteLoading = false;
  showDeleteConfirm = false;

  constructor(
    private fb: FormBuilder,
    public auth: AuthService,
    private router: Router
  ) {}

  ngOnInit(): void {
    this.user = this.auth.getCurrentUser();
    this.buildForms();
    // Always fetch fresh profile from API
    this.auth.getProfile().subscribe({
      next: u => { this.user = u; this.buildForms(); },
      error: () => {}
    });
  }

  private buildForms(): void {
    this.profileForm = this.fb.group({
      fullName: [this.user?.fullName || '', [Validators.required, Validators.minLength(2)]],
      mobile: [this.user?.mobile || '', [Validators.pattern(/^[6-9]\d{9}$/)]]
    });

    this.pwForm = this.fb.group({
      currentPassword: ['', Validators.required],
      newPassword: ['', [Validators.required, Validators.minLength(8)]],
      confirmPassword: ['', Validators.required]
    }, { validators: passwordMatchValidator });
  }

  get pf() { return this.profileForm.controls; }
  get pwf() { return this.pwForm.controls; }

  saveProfile(): void {
    if (this.profileForm.invalid) { this.profileForm.markAllAsTouched(); return; }
    this.profileLoading = true;
    this.profileSuccess = '';
    this.profileError = '';
    const { fullName, mobile } = this.profileForm.value;
    this.auth.updateProfile(fullName, mobile || undefined).subscribe({
      next: u => {
        this.profileLoading = false;
        this.user = u;
        this.profileSuccess = 'Profile updated successfully.';
        setTimeout(() => this.profileSuccess = '', 3000);
      },
      error: err => {
        this.profileLoading = false;
        this.profileError = err.error?.message || 'Failed to update profile.';
      }
    });
  }

  changePassword(): void {
    if (this.pwForm.invalid) { this.pwForm.markAllAsTouched(); return; }
    this.pwLoading = true;
    this.pwSuccess = '';
    this.pwError = '';
    const { currentPassword, newPassword } = this.pwForm.value;
    this.auth.changePassword(currentPassword, newPassword).subscribe({
      next: () => {
        this.pwLoading = false;
        this.pwSuccess = 'Password changed successfully.';
        this.pwForm.reset();
        setTimeout(() => this.pwSuccess = '', 4000);
      },
      error: err => {
        this.pwLoading = false;
        const code = err.error?.error;
        this.pwError = code === 'incorrect_current_password'
          ? 'Current password is incorrect.'
          : err.error?.message || 'Failed to change password.';
      }
    });
  }

  confirmDelete(): void {
    this.deleteLoading = true;
    this.auth.deleteAccount().subscribe({
      next: () => { this.deleteLoading = false; this.router.navigate(['/']); },
      error: () => { this.deleteLoading = false; this.showDeleteConfirm = false; }
    });
  }
}
