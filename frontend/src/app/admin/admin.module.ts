import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterModule, Routes } from '@angular/router';
import { AdminComponent } from './admin.component';
import { AdminService } from '../services/admin.service';

const routes: Routes = [
  { path: '', component: AdminComponent }
];

@NgModule({
  declarations: [AdminComponent],
  imports: [CommonModule, FormsModule, RouterModule.forChild(routes)],
  providers: [AdminService]
})
export class AdminModule {}
