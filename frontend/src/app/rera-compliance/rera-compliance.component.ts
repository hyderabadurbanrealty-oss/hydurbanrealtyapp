import { Component, Input, OnInit } from '@angular/core';

@Component({
  standalone: false,
  selector: 'app-rera-compliance',
  templateUrl: './rera-compliance.component.html',
  styleUrls: ['./rera-compliance.component.css']
})
export class ReraComplianceComponent implements OnInit {
  @Input() property: any;
  
  complianceScore: number = 0;
  complianceMetrics: any[] = [];
  documents: any[] = [];
  timelineCompliance: number = 0;
  fundUtilization: number = 0;
  complaintsCount: number = 0;
  overallStatus: string = '';
  
  ngOnInit(): void {
    if (this.property) {
      this.calculateCompliance();
    }
  }

  calculateCompliance(): void {
    this.calculateComplianceScore();
    this.buildComplianceMetrics();
    this.buildDocumentsList();
    this.calculateTimelineCompliance();
    this.calculateFundUtilization();
    this.calculateComplaints();
    this.setOverallStatus();
  }

  calculateComplianceScore(): number {
    let score = 0;
    
    // RERA Registration - check raw_data for registration details (30 points)
    const reraReg = this.property.rawData?.['RERA Registration Details']?.['RERA Registration Number'] 
                    || this.property.rawData?.['Registration Number']
                    || this.property.id; // Use project ID as fallback since it's based on RERA
    if (reraReg && reraReg.length > 5) {
      score += 30;
    }
    
    // Plan Approval (25 points) - check for plan approval number
    if (this.property.planApprovalNumber || this.property.rawData?.['Plan Approval Number']) {
      score += 25;
    }
    
    // Registration Date (20 points) - check approved_date
    if (this.property.approvedDate || this.property.rawData?.['Date of Registration']) {
      score += 20;
    }
    
    // Completion Date Specified (15 points)
    if (this.property.completionDate || this.property.revisedCompletionDate) {
      score += 15;
    }
    
    // Project Status (10 points)
    const status = (this.property.projectStatus || '').toLowerCase();
    if (status.includes('active') || status.includes('ongoing') || status.includes('completed') || status.includes('registered')) {
      score += 10;
    }
    
    this.complianceScore = Math.min(score, 100);
    return this.complianceScore;
  }

  buildComplianceMetrics(): void {
    const reraReg = this.property.rawData?.['RERA Registration Details']?.['RERA Registration Number'] 
                    || this.property.rawData?.['Registration Number']
                    || this.property.id;
    const planApprovalNumber = this.property.planApprovalNumber || this.property.rawData?.['Plan Approval Number'];
    
    // Check if plan is approved based on documents
    const hasPlanDocs = this.hasDoc(['Sanctioned Building Plan', 'Approval Layout Plan', 'Building Permit', 'Commencement Certificate']);
    const planApproved = planApprovalNumber || hasPlanDocs;
    
    const regDate = this.property.approvedDate || this.property.rawData?.['Date of Registration'];
    const completionDate = this.property.completionDate || this.property.revisedCompletionDate;
    
    this.complianceMetrics = [
      {
        label: 'RERA Registration',
        status: reraReg ? 'Verified' : 'Pending',
        icon: '📋',
        value: reraReg || 'Not Available',
        isGood: !!reraReg
      },
      {
        label: 'Plan Approval',
        status: planApproved ? 'Approved' : 'Pending',
        icon: '✅',
        value: planApprovalNumber || (hasPlanDocs ? 'Sanctioned Plans Available' : 'Awaiting Approval'),
        isGood: planApproved
      },
      {
        label: 'Registration Date',
        status: regDate ? 'Registered' : 'Not Registered',
        icon: '📅',
        value: regDate || 'N/A',
        isGood: !!regDate
      },
      {
        label: 'Expected Completion',
        status: completionDate ? 'Scheduled' : 'TBD',
        icon: '🎯',
        value: completionDate || 'To Be Decided',
        isGood: !!completionDate
      }
    ];
  }

  hasDoc(keywords: string[]): boolean {
    const docs: string[] = (this.property.availableDocuments || this.property.scrapedDocuments || []).map((d: string) => d.toLowerCase());
    return keywords.some(kw => docs.some((d: string) => d.includes(kw.toLowerCase())));
  }

  buildDocumentsList(): void {
    const reraReg = this.property.rawData?.['RERA Registration Details']?.['RERA Registration Number'] 
                    || this.property.rawData?.['Registration Number']
                    || this.property.id;
    const hasReraReg = !!reraReg;

    this.documents = [
      {
        name: 'RERA Certificate',
        status: hasReraReg ? 'Available' : 'Pending',
        icon: '📜',
        isAvailable: hasReraReg
      },
      {
        name: 'Building Plan Approval',
        status: this.hasDoc(['Sanctioned Building Plan', 'Approval Layout Plan', 'Building Permit', 'Proceeding Building Permission']) ? 'Uploaded' : 'Not Uploaded',
        icon: '📐',
        isAvailable: this.hasDoc(['Sanctioned Building Plan', 'Approval Layout Plan', 'Building Permit', 'Proceeding Building Permission'])
      },
      {
        name: 'Land Title Report',
        status: this.hasDoc(['legal title report', 'Land Title Search Report']) ? 'Uploaded' : 'Not Uploaded',
        icon: '📋',
        isAvailable: this.hasDoc(['legal title report', 'Land Title Search Report'])
      },
      {
        name: 'Encumbrance Details',
        status: this.hasDoc(['encumbrance']) ? 'Uploaded' : 'Not Uploaded',
        icon: '🔒',
        isAvailable: this.hasDoc(['encumbrance'])
      },
      {
        name: 'Commencement Certificate',
        status: this.hasDoc(['Commencement Certificate', 'Building Permit Proceedings']) ? 'Uploaded' : 'Not Uploaded',
        icon: '🏗️',
        isAvailable: this.hasDoc(['Commencement Certificate', 'Building Permit Proceedings'])
      },
      {
        name: 'Agreement for Sale',
        status: this.hasDoc(['allotment letter', 'agreement for sale', 'Agreement of Sale']) ? 'Uploaded' : 'Not Uploaded',
        icon: '📝',
        isAvailable: this.hasDoc(['allotment letter', 'agreement for sale', 'Agreement of Sale'])
      },
      {
        name: 'Declaration Form B',
        status: this.hasDoc(['FORM B', 'Declaration in FORM']) ? 'Uploaded' : 'Not Uploaded',
        icon: '📄',
        isAvailable: this.hasDoc(['FORM B', 'Declaration in FORM'])
      },
      {
        name: "Architect's Certificate",
        status: this.hasDoc(['Architects certificate', 'Form 4', 'Form–1A']) ? 'Uploaded' : 'Not Uploaded',
        icon: '🏛️',
        isAvailable: this.hasDoc(['Architects certificate', 'Form 4', 'Form–1A'])
      }
    ];
  }

  calculateTimelineCompliance(): void {
    const regDate = this.parseDate(this.property.approvedDate || this.property.rawData?.['Date of Registration'] || '');
    const compDate = this.parseDate(this.property.completionDate || this.property.revisedCompletionDate || '');
    const today = new Date();
    
    if (regDate && compDate) {
      const totalDuration = compDate.getTime() - regDate.getTime();
      const elapsed = today.getTime() - regDate.getTime();
      const progress = (elapsed / totalDuration) * 100;
      
      // If behind schedule, reduce compliance
      if (today > compDate && this.property.projectStatus?.toLowerCase() !== 'completed') {
        this.timelineCompliance = Math.max(0, 100 - ((today.getTime() - compDate.getTime()) / (1000 * 60 * 60 * 24 * 365)) * 20);
      } else if (progress > 100) {
        this.timelineCompliance = 100;
      } else {
        this.timelineCompliance = Math.min(100, progress + 20); // Bonus for being on track
      }
    } else {
      this.timelineCompliance = 50; // Default when dates not available
    }
    
    this.timelineCompliance = Math.round(this.timelineCompliance);
  }

  calculateFundUtilization(): void {
    // Simulate fund utilization based on project progress
    const status = (this.property.projectStatus || '').toLowerCase();
    
    if (status.includes('completed')) {
      this.fundUtilization = 95 + Math.random() * 5;
    } else if (status.includes('ongoing')) {
      this.fundUtilization = 50 + Math.random() * 30;
    } else {
      this.fundUtilization = 10 + Math.random() * 20;
    }
    
    this.fundUtilization = Math.round(this.fundUtilization);
  }

  calculateComplaints(): void {
    // Simulate complaints count based on reviews
    const reviewCount = parseInt(this.property.reviewCount) || 0;
    const rating = parseFloat(this.property.averageRating) || 0;
    
    // Lower rating = more complaints
    if (rating >= 4) {
      this.complaintsCount = Math.floor(reviewCount * 0.05); // 5% complaint rate
    } else if (rating >= 3) {
      this.complaintsCount = Math.floor(reviewCount * 0.15); // 15% complaint rate
    } else {
      this.complaintsCount = Math.floor(reviewCount * 0.30); // 30% complaint rate
    }
  }

  setOverallStatus(): void {
    if (this.complianceScore >= 90) {
      this.overallStatus = 'Fully Compliant';
    } else if (this.complianceScore >= 70) {
      this.overallStatus = 'Mostly Compliant';
    } else if (this.complianceScore >= 50) {
      this.overallStatus = 'Partially Compliant';
    } else {
      this.overallStatus = 'Non-Compliant';
    }
  }

  parseDate(dateStr: string): Date | null {
    if (!dateStr) return null;
    const parts = dateStr.split('/');
    if (parts.length === 3) {
      return new Date(parseInt(parts[2]), parseInt(parts[1]) - 1, parseInt(parts[0]));
    }
    return null;
  }

  getComplianceColor(): string {
    if (this.complianceScore >= 90) return '#10b981';
    if (this.complianceScore >= 70) return '#3b82f6';
    if (this.complianceScore >= 50) return '#f59e0b';
    return '#ef4444';
  }

  getStatusClass(status: string): string {
    const lowerStatus = status.toLowerCase();
    if (lowerStatus.includes('verified') || lowerStatus.includes('approved') || lowerStatus.includes('available') || lowerStatus.includes('registered')) {
      return 'good';
    }
    if (lowerStatus.includes('pending') || lowerStatus.includes('awaiting')) {
      return 'warning';
    }
    return 'neutral';
  }

  getDocumentStatusClass(isAvailable: boolean): string {
    return isAvailable ? 'available' : 'pending';
  }
}
