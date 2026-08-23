import { Component } from '@angular/core';

@Component({
  selector: 'app-about',
  templateUrl: './about.component.html',
  styleUrls: ['./about.component.css']
})
export class AboutComponent {
  showEnquiryModal = false;

  openEnquiryModal(): void {
    this.showEnquiryModal = true;
  }

  closeEnquiryModal(): void {
    this.showEnquiryModal = false;
  }
}
