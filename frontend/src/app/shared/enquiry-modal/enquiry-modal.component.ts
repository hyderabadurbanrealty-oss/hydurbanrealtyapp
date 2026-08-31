import { Component, EventEmitter, Input, Output } from '@angular/core';
import { HttpClient } from '@angular/common/http';

export interface EnquiryFormData {
  name: string;
  email: string;
  mobile: string;
  interest: string;
}

@Component({
  standalone: false,
  selector: 'app-enquiry-modal',
  templateUrl: './enquiry-modal.component.html',
  styleUrls: ['./enquiry-modal.component.css']
})
export class EnquiryModalComponent {
  @Input() show = false;
  @Input() source = 'modal';
  @Output() close = new EventEmitter<void>();

  enquiryForm: EnquiryFormData = { name: '', email: '', mobile: '', interest: '' };
  enquirySubmitting = false;
  enquirySuccess = false;
  enquiryError = '';
  enquiryCaptchaA = 0;
  enquiryCaptchaB = 0;
  enquiryCaptchaAnswer: number | string | null = null;

  constructor(private http: HttpClient) {
    this.refreshCaptcha();
  }

  get enquiryCaptchaValid(): boolean {
    return this.enquiryCaptchaAnswer !== null &&
           this.enquiryCaptchaAnswer !== '' &&
           +this.enquiryCaptchaAnswer === this.enquiryCaptchaA + this.enquiryCaptchaB;
  }

  ngOnChanges() {
    if (this.show) {
      this.resetForm();
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
  }

  resetForm(): void {
    this.enquirySuccess = false;
    this.enquiryError = '';
    this.enquiryForm = { name: '', email: '', mobile: '', interest: '' };
    this.refreshCaptcha();
  }

  closeModal(): void {
    this.close.emit();
  }

  refreshCaptcha(): void {
    this.enquiryCaptchaA = Math.floor(Math.random() * 9) + 1;
    this.enquiryCaptchaB = Math.floor(Math.random() * 9) + 1;
    this.enquiryCaptchaAnswer = null;
  }

  submitEnquiry(): void {
    this.enquiryError = '';
    
    // Validate required fields
    if (!this.enquiryForm.name.trim() || !this.enquiryForm.email.trim() || !this.enquiryForm.mobile.trim()) {
      this.enquiryError = 'Name, email, and mobile number are required.'; 
      return;
    }
    
    // Validate email format
    const emailRegex = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
    if (!emailRegex.test(this.enquiryForm.email.trim())) {
      this.enquiryError = 'Please enter a valid email address.'; 
      return;
    }
    
    // Validate mobile format
    if (!/^\d{10}$/.test(this.enquiryForm.mobile.trim())) {
      this.enquiryError = 'Enter a valid 10-digit mobile number.'; 
      return;
    }
    
    // Validate captcha
    if (!this.enquiryCaptchaValid) {
      this.enquiryError = 'Please answer the verification question correctly.'; 
      return;
    }
    
    this.enquirySubmitting = true;
    
    this.http.post('/api/submit_lead', {
      name: this.enquiryForm.name.trim(),
      email: this.enquiryForm.email.trim(),
      mobile: this.enquiryForm.mobile.trim(),
      areaOfInterest: this.enquiryForm.interest || 'General Enquiry',
      source: this.source
    }).subscribe({
      next: () => { 
        this.enquirySubmitting = false; 
        this.enquirySuccess = true;
      },
      error: (err) => {
        this.enquirySubmitting = false;
        const errorMessage = err?.error?.message || 'Could not submit. Please try again or call us directly.';
        this.enquiryError = errorMessage;
      }
    });
  }
}
