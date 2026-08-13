import { Component, OnInit } from '@angular/core';
import { ChartData, ChartOptions } from 'chart.js';

type CalcMode = 'home-loan' | 'nri' | 'affordability' | 'compare';
type Currency = 'INR' | 'USD' | 'AED' | 'GBP' | 'EUR' | 'SGD' | 'AUD' | 'CAD';

interface LoanResult {
  emi: number;
  totalPayment: number;
  totalInterest: number;
  principalPct: number;
  interestPct: number;
  schedule: ScheduleRow[];
}

interface ScheduleRow {
  year: number;
  openingBalance: number;
  principal: number;
  interest: number;
  closingBalance: number;
  cumPrincipal: number;
  cumInterest: number;
}

interface BankRate {
  bank: string;
  minRate: number;
  maxRate: number;
  type: string;
  tag: string;
}

interface NriInfo {
  countryCode: string;
  countryName: string;
  currency: Currency;
  symbol: string;
  forexToInr: number;
  taxTds: number;
  nriScheme: string;
  tipText: string;
}

@Component({
  selector: 'app-loan-calculator',
  templateUrl: './loan-calculator.component.html',
  styleUrls: ['./loan-calculator.component.css']
})
export class LoanCalculatorComponent implements OnInit {

  Math = Math;
  activeMode: CalcMode = 'home-loan';

  // ── Home Loan inputs ───────────────────────────────────────────────
  loanAmount     = 6000000;   // ₹60L
  interestRate   = 8.5;
  tenureYears    = 20;
  downPaymentPct = 20;
  propertyValue  = 7500000;

  // ── NRI inputs ─────────────────────────────────────────────────────
  selectedNriCountry: NriInfo;
  foreignIncome     = 0;
  nriLoanAmount     = 10000000;
  nriInterestRate   = 9.0;
  nriTenureYears    = 15;
  showForexHelper   = false;
  forexAmount       = 100000;

  // ── Affordability ──────────────────────────────────────────────────
  monthlyIncome    = 200000;
  existingEmi      = 0;
  affordRate       = 8.5;
  affordTenure     = 20;
  foir             = 0.4;   // Fixed Obligation to Income Ratio (40% standard)

  // ── Compare Loans ──────────────────────────────────────────────────
  cmpAmount  = 6000000;
  cmpTenure  = 20;
  bank1Rate  = 8.4;
  bank2Rate  = 9.0;
  bank3Rate  = 8.7;

  // ── Results ────────────────────────────────────────────────────────
  result?: LoanResult;
  nriResult?: LoanResult;
  affordResult: { maxLoan: number; maxEmi: number; maxProperty: number } | null = null;
  cmpResults: { bank: string; rate: number; emi: number; totalInterest: number }[] = [];

  // ── Amortisation view ──────────────────────────────────────────────
  showSchedule = false;
  scheduleView: 'table' | 'chart' = 'chart';

  // ── Interest rates data (RBI + top lenders, Aug 2026) ─────────────
  readonly bankRates: BankRate[] = [
    { bank: 'SBI',           minRate: 8.50, maxRate: 9.85,  type: 'Floating', tag: 'PSU'      },
    { bank: 'HDFC Bank',     minRate: 8.75, maxRate: 9.65,  type: 'Floating', tag: 'Private'  },
    { bank: 'ICICI Bank',    minRate: 8.75, maxRate: 9.80,  type: 'Floating', tag: 'Private'  },
    { bank: 'Axis Bank',     minRate: 8.75, maxRate: 9.90,  type: 'Floating', tag: 'Private'  },
    { bank: 'Kotak Mahindra',minRate: 8.75, maxRate: 9.75,  type: 'Floating', tag: 'Private'  },
    { bank: 'Bank of Baroda',minRate: 8.40, maxRate: 10.65, type: 'Floating', tag: 'PSU'      },
    { bank: 'LIC Housing',   minRate: 8.50, maxRate: 10.75, type: 'Both',     tag: 'HFC'      },
    { bank: 'PNB Housing',   minRate: 8.50, maxRate: 14.50, type: 'Both',     tag: 'HFC'      },
    { bank: 'Canara Bank',   minRate: 8.40, maxRate: 11.25, type: 'Floating', tag: 'PSU'      },
    { bank: 'Union Bank',    minRate: 8.35, maxRate: 10.90, type: 'Floating', tag: 'PSU'      },
    { bank: 'Bajaj Housing', minRate: 8.50, maxRate: 15.00, type: 'Both',     tag: 'NBFC'     },
    { bank: 'Tata Capital',  minRate: 8.75, maxRate: 14.00, type: 'Both',     tag: 'NBFC'     },
  ];

  readonly nriCountries: NriInfo[] = [
    { countryCode: 'AE', countryName: 'UAE',           currency: 'AED', symbol: 'د.إ', forexToInr: 22.8,  taxTds: 30, nriScheme: 'NRE/NRO/FCNR',   tipText: 'UAE residents get preferential NRI rates at SBI, ICICI & Axis. Remittance via NEFT/SWIFT.'  },
    { countryCode: 'US', countryName: 'United States', currency: 'USD', symbol: '$',   forexToInr: 83.5,  taxTds: 30, nriScheme: 'NRE/NRO/FCNR',   tipText: 'FBAR reporting required. Use NRE account for tax-free repatriation. FIRPTA applies on sale.' },
    { countryCode: 'GB', countryName: 'United Kingdom',currency: 'GBP', symbol: '£',   forexToInr: 105.2, taxTds: 30, nriScheme: 'NRE/NRO/FCNR',   tipText: 'HMRC may require reporting rental income. Use SWIFT/Wise for cost-effective remittance.'     },
    { countryCode: 'SG', countryName: 'Singapore',     currency: 'SGD', symbol: 'S$',  forexToInr: 62.3,  taxTds: 30, nriScheme: 'NRE/NRO',        tipText: 'Singapore-India DTAA benefits available. IBU loans from Indian banks in Singapore.'          },
    { countryCode: 'AU', countryName: 'Australia',     currency: 'AUD', symbol: 'A$',  forexToInr: 54.8,  taxTds: 30, nriScheme: 'NRE/NRO/FCNR',   tipText: 'FIRB approval required. Rental income taxed at 30% TDS in India; claim DTAA relief.'         },
    { countryCode: 'CA', countryName: 'Canada',        currency: 'CAD', symbol: 'C$',  forexToInr: 61.7,  taxTds: 30, nriScheme: 'NRE/NRO/FCNR',   tipText: 'Canada-India DTAA limits double taxation. FINTRAC rules apply for wire transfers above C$10k.' },
    { countryCode: 'EU', countryName: 'Europe (EUR)',  currency: 'EUR', symbol: '€',   forexToInr: 90.4,  taxTds: 30, nriScheme: 'NRE/NRO/FCNR',   tipText: 'SEPA remittances are cost-effective. Declare property in annual IT return via Schedule FA.'    },
    { countryCode: 'SA', countryName: 'Saudi Arabia',  currency: 'AED', symbol: 'SAR', forexToInr: 22.2,  taxTds: 30, nriScheme: 'NRE/NRO',        tipText: 'Gulf NRIs can remit via IMPS/NEFT. SBI Gulf & ICICI offer branch support in Riyadh.'          },
  ];

  // ── Chart data ─────────────────────────────────────────────────────
  doughnutData: ChartData<'doughnut'> = { labels: [], datasets: [] };
  doughnutOptions: ChartOptions<'doughnut'> = {
    responsive: true, maintainAspectRatio: false, cutout: '72%',
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          label: (ctx) => {
            const val = ctx.parsed as number;
            return `  ₹${val.toLocaleString('en-IN')}`;
          }
        }
      }
    }
  };

  amortChartData: ChartData<'bar'> = { labels: [], datasets: [] };
  amortChartOptions: ChartOptions<'bar'> = {
    responsive: true, maintainAspectRatio: false,
    plugins: {
      legend: { display: true, position: 'top', labels: { color: '#64748b', font: { size: 12 }, boxWidth: 12 } },
      tooltip: { callbacks: { label: (ctx) => `  ₹${Math.round(ctx.parsed.y).toLocaleString('en-IN')}` } }
    },
    scales: {
      x: { stacked: true, grid: { display: false }, ticks: { color: '#64748b', font: { size: 11 } } },
      y: { stacked: true, grid: { color: 'rgba(148,163,184,0.1)' },
           ticks: { color: '#64748b', font: { size: 11 }, callback: (v) => `₹${(+v / 100000).toFixed(0)}L` }
      }
    }
  };

  ngOnInit(): void {
    this.selectedNriCountry = this.nriCountries[0];
    this.calculate();
  }

  setMode(mode: CalcMode): void {
    this.activeMode = mode;
    this.showSchedule = false;
    if (mode === 'home-loan') this.calculate();
    if (mode === 'nri')       this.calculateNri();
    if (mode === 'affordability') this.calculateAffordability();
    if (mode === 'compare')   this.calculateCompare();
  }

  // ── Core EMI formula ───────────────────────────────────────────────
  calcEmi(principal: number, annualRate: number, years: number): number {
    if (principal <= 0 || annualRate <= 0 || years <= 0) return 0;
    const r = annualRate / 100 / 12;
    const n = years * 12;
    return principal * r * Math.pow(1 + r, n) / (Math.pow(1 + r, n) - 1);
  }

  buildResult(principal: number, annualRate: number, years: number): LoanResult {
    const emi           = this.calcEmi(principal, annualRate, years);
    const totalPayment  = emi * years * 12;
    const totalInterest = totalPayment - principal;
    const principalPct  = Math.round((principal / totalPayment) * 100);
    const interestPct   = 100 - principalPct;

    // Build annual amortisation schedule
    const schedule: ScheduleRow[] = [];
    let balance = principal;
    let cumPrincipal = 0;
    let cumInterest  = 0;
    const r = annualRate / 100 / 12;

    for (let yr = 1; yr <= years; yr++) {
      const opening = balance;
      let yearPrincipal = 0;
      let yearInterest  = 0;
      for (let m = 0; m < 12 && balance > 0; m++) {
        const intPmt = balance * r;
        const prinPmt = Math.min(emi - intPmt, balance);
        yearInterest  += intPmt;
        yearPrincipal += prinPmt;
        balance       -= prinPmt;
        if (balance < 1) balance = 0;
      }
      cumPrincipal += yearPrincipal;
      cumInterest  += yearInterest;
      schedule.push({
        year: yr,
        openingBalance: opening,
        principal: yearPrincipal,
        interest: yearInterest,
        closingBalance: balance,
        cumPrincipal,
        cumInterest
      });
    }
    return { emi, totalPayment, totalInterest, principalPct, interestPct, schedule };
  }

  calculate(): void {
    this.result = this.buildResult(this.loanAmount, this.interestRate, this.tenureYears);
    this.buildDoughnut(this.result);
    this.buildAmortChart(this.result);
  }

  calculateNri(): void {
    this.nriResult = this.buildResult(this.nriLoanAmount, this.nriInterestRate, this.nriTenureYears);
    this.buildDoughnut(this.nriResult);
    this.buildAmortChart(this.nriResult);
  }

  calculateAffordability(): void {
    const availableEmi = (this.monthlyIncome * this.foir) - this.existingEmi;
    if (availableEmi <= 0) { this.affordResult = { maxLoan: 0, maxEmi: 0, maxProperty: 0 }; return; }
    const r = this.affordRate / 100 / 12;
    const n = this.affordTenure * 12;
    const maxLoan = availableEmi * (Math.pow(1 + r, n) - 1) / (r * Math.pow(1 + r, n));
    const maxProperty = maxLoan / (1 - this.downPaymentPct / 100);
    this.affordResult = { maxLoan: Math.round(maxLoan), maxEmi: Math.round(availableEmi), maxProperty: Math.round(maxProperty) };
  }

  calculateCompare(): void {
    const banks = [
      { bank: 'Bank A', rate: this.bank1Rate },
      { bank: 'Bank B', rate: this.bank2Rate },
      { bank: 'Bank C', rate: this.bank3Rate },
    ];
    this.cmpResults = banks.map(b => {
      const emi   = this.calcEmi(this.cmpAmount, b.rate, this.cmpTenure);
      const total = emi * this.cmpTenure * 12;
      return { bank: b.bank, rate: b.rate, emi: Math.round(emi), totalInterest: Math.round(total - this.cmpAmount) };
    });
  }

  private buildDoughnut(r: LoanResult): void {
    this.doughnutData = {
      labels: ['Principal', 'Total Interest'],
      datasets: [{
        data: [Math.round(this.loanAmount), Math.round(r.totalInterest)],
        backgroundColor: ['#0d3b73', '#f59e0b'],
        borderWidth: 0,
        hoverOffset: 6
      }]
    };
  }

  private buildAmortChart(r: LoanResult): void {
    const years = r.schedule.map(s => `Yr ${s.year}`);
    this.amortChartData = {
      labels: years,
      datasets: [
        {
          label: 'Principal',
          data: r.schedule.map(s => Math.round(s.principal)),
          backgroundColor: 'rgba(13,59,115,0.85)',
          borderRadius: 2
        },
        {
          label: 'Interest',
          data: r.schedule.map(s => Math.round(s.interest)),
          backgroundColor: 'rgba(245,158,11,0.85)',
          borderRadius: 2
        }
      ]
    };
  }

  // ── Helpers ────────────────────────────────────────────────────────
  get loanAmountLakhs(): number { return this.loanAmount / 100000; }
  set loanAmountLakhs(v: number) { this.loanAmount = Math.round(v * 100000); }

  get nriLoanAmountLakhs(): number { return this.nriLoanAmount / 100000; }
  set nriLoanAmountLakhs(v: number) { this.nriLoanAmount = Math.round(v * 100000); }

  get downPaymentAmount(): number { return Math.round(this.propertyValue * this.downPaymentPct / 100); }
  get derivedLoanAmount(): number { return this.propertyValue - this.downPaymentAmount; }

  applyPropertyValue(): void {
    this.loanAmount = this.derivedLoanAmount;
    this.calculate();
  }

  get forexInInr(): number {
    return Math.round(this.forexAmount * this.selectedNriCountry.forexToInr);
  }

  onNriCountryChange(): void {
    this.calculateNri();
  }

  fmtCr(val: number): string {
    if (val >= 10000000) return `₹${(val / 10000000).toFixed(2)} Cr`;
    if (val >= 100000)   return `₹${(val / 100000).toFixed(2)} L`;
    return `₹${Math.round(val).toLocaleString('en-IN')}`;
  }

  fmtInr(val: number): string {
    return `₹${Math.round(val).toLocaleString('en-IN')}`;
  }

  selectBankRate(rate: number): void {
    if (this.activeMode === 'home-loan') {
      this.interestRate = rate;
      this.calculate();
    } else if (this.activeMode === 'nri') {
      this.nriInterestRate = rate;
      this.calculateNri();
    } else if (this.activeMode === 'affordability') {
      this.affordRate = rate;
      this.calculateAffordability();
    } else if (this.activeMode === 'compare') {
      // Apply to all three bank rate slots so comparison updates
      this.bank1Rate = rate;
      this.bank2Rate = +(rate + 0.25).toFixed(2);
      this.bank3Rate = +(rate + 0.50).toFixed(2);
      this.calculateCompare();
    }
    // Scroll to top of results smoothly
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  get minBankRate(): number {
    return Math.min(...this.bankRates.map(b => b.minRate));
  }
}
