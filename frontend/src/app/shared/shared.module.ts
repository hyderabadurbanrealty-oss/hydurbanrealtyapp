import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { EnquiryModalComponent } from './enquiry-modal/enquiry-modal.component';
import { ScheduleVisitModalComponent } from '../schedule-visit-modal/schedule-visit-modal.component';
import { ReplacePipe } from '../replace.pipe';
import { SafePipe } from '../safe.pipe';

@NgModule({
  declarations: [
    EnquiryModalComponent,
    ScheduleVisitModalComponent,
    ReplacePipe,
    SafePipe,
  ],
  imports: [CommonModule, FormsModule],
  exports: [
    EnquiryModalComponent,
    ScheduleVisitModalComponent,
    ReplacePipe,
    SafePipe,
  ],
})
export class SharedModule {}
