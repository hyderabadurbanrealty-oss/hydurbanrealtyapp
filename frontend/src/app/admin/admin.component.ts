import { Component, OnInit, OnDestroy } from '@angular/core';
import { Router } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { PropertyService } from '../services/property.service';
import { AdminService } from '../services/admin.service';
import { AuthService } from '../services/auth.service';
import { MediaService } from '../services/media.service';

interface PricingUnit {
  type: string;
  size: string;
  pricePerSqft: number;
  minPrice: number;
  maxPrice: number;
}

@Component({
  selector: 'app-admin',
  templateUrl: './admin.component.html',
  styleUrls: ['./admin.component.css']
})
export class AdminComponent implements OnInit, OnDestroy {

  // ── Auth ───────────────────────────────────────────────────────────────────
  isLoggedIn = false;
  loginUsername = '';
  loginPassword = '';
  loginError = '';
  loginLoading = false;

  // ── UI state ───────────────────────────────────────────────────────────────
  activeSection: 'dashboard' | 'properties' | 'users' | 'leads' | 'visits' | 'scraper' | 'social' | 'resale' | 'reviews' = 'dashboard';
  statusMsg = '';
  loading = false;

  // ── Sidebar state ──────────────────────────────────────────────────────────
  sidebarOpen      = false;   // mobile: slide-in overlay
  sidebarCollapsed = false;   // desktop: icon-only collapse

  // ── Dashboard stats ────────────────────────────────────────────────────────
  dashStats: any = null;

  // ── Properties ────────────────────────────────────────────────────────────
  properties: any[] = [];
  filteredProperties: any[] = [];
  propertySearchQuery = '';

  showEditModal = false;
  showPricingModal = false;
  showCreateModal = false;
  selectedProperty: any = null;
  editForm: any = {};
  createForm: any = {
    'Project Name': '', 'Project Status': 'New Project',
    'Project Type': 'Residential', 'Locality': '',
    'District': '', 'Pin Code': '', 'State': 'Telangana',
    'Total Area(In sqmts)': ''
  };
  pricingUnits: PricingUnit[] = [];
  priceHistoryLog: any[] = [];
  newUnit: PricingUnit = { type: '2 BHK', size: '', pricePerSqft: 0, minPrice: 0, maxPrice: 0 };
  unitTypes = ['1 BHK', '2 BHK', '3 BHK', '4 BHK', 'Penthouse', 'Villa', 'Plot', 'Duplex'];

  // ── Media ─────────────────────────────────────────────────────────────────
  showMediaModal = false;
  mediaTab: 'image' | 'floorplan' | 'document' | 'video' = 'image';
  allMedia: any[] = [];
  mediaLoading = false;
  uploadQueue: File[] = [];
  uploading = false;
  videoUrl = '';
  videoTitle = '';
  imageUrlInput = '';
  imageUrlTitle = '';
  editingMediaId: string | null = null;
  editingMediaTitle = '';

  // ── Scraped floor plans ───────────────────────────────────────────────────
  scrapedFloorPlans: any[] = [];      // raw entries from manifest.json
  scrapedLoading = false;
  promotingPage: string | null = null; // filename being promoted

  // ── Users ─────────────────────────────────────────────────────────────────
  users: any[] = [];
  filteredUsers: any[] = [];
  userSearchQuery = '';
  userPage = 1;
  userTotal = 0;
  userStats: any = null;
  showUserEditModal = false;
  selectedUser: any = null;
  userEditRole = 'user';

  // ── Leads ─────────────────────────────────────────────────────────────────
  leads: any[] = [];
  filteredLeads: any[] = [];
  leadsSearchQuery = '';
  leadsLoading = false;
  leadPage = 1;
  leadTotal = 0;

  // ── Visits ─────────────────────────────────────────────────────────────────
  visits: any[] = [];
  filteredVisits: any[] = [];
  visitsSearchQuery = '';
  visitsLoading = false;

  // ── Scraper ────────────────────────────────────────────────────────────────
  preferences: { pincodes: string[]; igrs_username: string; igrs_password: string } = { pincodes: [], igrs_username: '', igrs_password: '' };
  showIgrsPassword = false;
  newPincode = '';
  prefsLoading = false;
  prefsSaved = false;
  rrScrapeStatus: any = null;
  rrScrapeLoading = false;
  sroScrapeStatus: any = null;
  sroScrapeLoading = false;
  private _rrPoller: any = null;
  private _sroPoller: any = null;

  // ── Social tweets ─────────────────────────────────────────────────────────
  tweets: any[] = [];
  tweetsLoading = false;
  tweetsError = '';
  newTweetUrl   = '';
  newTweetLabel = '';
  addingTweet   = false;
  addTweetError = '';
  addTweetSuccess = '';

  // ── Resale listings ───────────────────────────────────────────────────────
  resaleListings: any[] = [];
  resaleLoading  = false;
  resaleFilter   = 'all';
  resaleSearch   = '';
  resaleUpdating: string | null = null;

  // ── Reviews ───────────────────────────────────────────────────────────────
  adminReviews: any[]  = [];
  reviewsLoading       = false;
  reviewsFilter: 'all' | 'pending' | 'approved' = 'pending';
  reviewsSearch        = '';

  constructor(
    private adminService: AdminService,
    private propertyService: PropertyService,
    private authService: AuthService,
    private mediaService: MediaService,
    private router: Router,
    private http: HttpClient
  ) {}

  ngOnInit() {
    const user = this.authService.getCurrentUser();
    this.isLoggedIn = (user?.role === 'admin') ||
      (localStorage.getItem('isAdmin') === 'true' && !!this.authService.getAccessToken());
    if (this.isLoggedIn) {
      this.loadDashboard();
      this.loadProperties();
      this.loadLeads();
      this.loadPreferences();
      this.pollRrStatus();
      this.pollSroStatus();
    }
  }

  ngOnDestroy() {
    if (this._rrPoller)  clearInterval(this._rrPoller);
    if (this._sroPoller) clearInterval(this._sroPoller);
  }

  // ── Auth ───────────────────────────────────────────────────────────────────

  doLogin() {
    this.loginError = '';
    this.loginLoading = true;
    this.authService.login(this.loginUsername, this.loginPassword).subscribe({
      next: (resp: any) => {
        if (resp.user?.role !== 'admin') {
          this.authService.clearSession();
          this.loginError = 'Access denied: admin account required';
          this.loginLoading = false;
          return;
        }
        this.isLoggedIn = true;
        this.loginLoading = false;
        this.loadDashboard();
        this.loadProperties();
        this.loadLeads();
        this.loadPreferences();
        this.pollRrStatus();
        this.pollSroStatus();
      },
      error: () => {
        // Fallback: legacy /api/login for username-based admins
        this.propertyService.login(this.loginUsername, this.loginPassword).subscribe({
          next: (res: any) => {
            if (res.token) localStorage.setItem('authToken', res.token);
            localStorage.setItem('isAdmin', 'true');
            this.isLoggedIn = true;
            this.loginLoading = false;
            this.loadDashboard();
            this.loadProperties();
            this.loadLeads();
            this.loadPreferences();
            this.pollRrStatus();
            this.pollSroStatus();
          },
          error: err => {
            this.loginError = err.error?.message || 'Invalid credentials';
            this.loginLoading = false;
          }
        });
      }
    });
  }

  logout() {
    this.authService.logout().subscribe();
    localStorage.removeItem('isAdmin');
    this.isLoggedIn = false;
    this.loginUsername = '';
    this.loginPassword = '';
  }

  // ── Dashboard ──────────────────────────────────────────────────────────────

  loadDashboard() {
    this.adminService.getDashboard().subscribe({
      next: s => this.dashStats = s,
      error: () => {}
    });
    this.adminService.getUserStats().subscribe({
      next: s => this.userStats = s,
      error: () => {}
    });
  }

  // ── Properties ────────────────────────────────────────────────────────────

  loadProperties() {
    this.loading = true;
    this.adminService.getAdminProperties().subscribe({
      next: (props: any[]) => {
        this.properties = props;
        this.filteredProperties = props;
        this.loading = false;
      },
      error: () => { this.statusMsg = 'Error loading properties'; this.loading = false; }
    });
  }

  searchProperties() {
    const q = this.propertySearchQuery.toLowerCase();
    this.filteredProperties = q
      ? this.properties.filter(p =>
          (p['Project Name'] || '').toLowerCase().includes(q) ||
          (p['Locality'] || p.locality || '').toLowerCase().includes(q) ||
          (p['District'] || p.district || '').toLowerCase().includes(q))
      : [...this.properties];
  }

  openCreateModal() {
    this.createForm = {
      'Project Name': '', 'Project Status': 'New Project',
      'Project Type': 'Residential', 'Locality': '',
      'District': '', 'Pin Code': '', 'State': 'Telangana',
      'Total Area(In sqmts)': ''
    };
    this.showCreateModal = true;
  }

  createProject() {
    if (!this.createForm['Project Name']) { this.statusMsg = 'Project Name is required'; return; }
    this.loading = true;
    this.adminService.createProperty(this.createForm).subscribe({
      next: () => { this.statusMsg = '✅ Property created'; this.loading = false; this.showCreateModal = false; this.loadProperties(); },
      error: err => { this.statusMsg = '❌ ' + (err.error?.message || 'Error creating property'); this.loading = false; }
    });
  }

  openEditModal(property: any) {
    this.selectedProperty = property;
    this.editForm = {
      project_name:        property['Project Name']        || property.project_name        || '',
      project_status:      property['Project Status']      || property.project_status      || '',
      project_type:        property['Project Type']        || property.project_type        || '',
      locality:            property['Locality']            || property.locality            || '',
      district:            property['District']            || property.district            || '',
      pin_code:            property['Pin Code']            || property.pin_code            || '',
      total_area_sqmt:     property['Total Area(In sqmts)'] || '',
      promoter_name:       property['Name']                || property.promoter_name       || '',
      bank_name:           property['Bank Name']           || property.bank_name           || '',
    };
    this.showEditModal = true;
  }

  saveProjectDetails() {
    if (!this.selectedProperty) return;
    const id = this.selectedProperty.id || this.selectedProperty.projectId;
    this.loading = true;
    this.adminService.updateProperty(id, this.editForm).subscribe({
      next: () => { this.statusMsg = '✅ Property updated'; this.loading = false; this.showEditModal = false; this.loadProperties(); },
      error: err => { this.statusMsg = '❌ ' + (err.error?.message || 'Error updating property'); this.loading = false; }
    });
  }

  openPricingModal(property: any) {
    this.selectedProperty = property;
    this.pricingUnits = [];
    this.priceHistoryLog = [];
    this.loading = true;
    const id = property.id || property.projectId;
    this.adminService.getAdminProperties().subscribe({
      next: (props: any[]) => {
        const full = props.find(p => (p.id || p.projectId) === id);
        this.pricingUnits = full?.pricing?.units || [];
        this.showPricingModal = true;
        this.loading = false;
      },
      error: () => { this.pricingUnits = []; this.showPricingModal = true; this.loading = false; }
    });
    this.propertyService.getPriceHistory(id).subscribe({
      next: h => this.priceHistoryLog = Array.isArray(h) ? h.slice().reverse() : [],
      error: () => { this.priceHistoryLog = []; }
    });
  }

  addPricingUnit() {
    if (this.newUnit.type && this.newUnit.pricePerSqft > 0) {
      this.pricingUnits.push({ ...this.newUnit });
      this.newUnit = { type: '2 BHK', size: '', pricePerSqft: 0, minPrice: 0, maxPrice: 0 };
    }
  }

  removePricingUnit(index: number) { this.pricingUnits.splice(index, 1); }

  savePricing() {
    if (!this.selectedProperty) return;
    const id = this.selectedProperty.id || this.selectedProperty.projectId;
    const pricing = { units: this.pricingUnits, lastUpdated: new Date().toISOString() };
    this.loading = true;
    this.adminService.updatePricing(id, pricing).subscribe({
      next: () => { this.statusMsg = '✅ Pricing updated'; this.loading = false; this.showPricingModal = false; this.loadProperties(); },
      error: err => { this.statusMsg = '❌ Error updating pricing'; this.loading = false; }
    });
  }

  deleteProperty(property: any) {
    if (!confirm(`Delete "${property['Project Name'] || property.project_name}"? This cannot be undone.`)) return;
    const id = property.id || property.projectId;
    this.loading = true;
    this.adminService.deleteProperty(id).subscribe({
      next: () => { this.statusMsg = '✅ Property deleted'; this.loading = false; this.loadProperties(); },
      error: err => { this.statusMsg = '❌ Error deleting property'; this.loading = false; }
    });
  }

  // ── Users ─────────────────────────────────────────────────────────────────

  loadUsers() {
    this.loading = true;
    this.adminService.getUsers(this.userPage).subscribe({
      next: res => {
        this.users = res.users;
        this.userTotal = res.total;
        this.filteredUsers = res.users;
        this.loading = false;
      },
      error: () => { this.statusMsg = 'Error loading users'; this.loading = false; }
    });
  }

  searchUsers() {
    const q = this.userSearchQuery.toLowerCase();
    this.filteredUsers = q
      ? this.users.filter(u =>
          (u.fullName || u.email || '').toLowerCase().includes(q) ||
          (u.email || '').toLowerCase().includes(q))
      : [...this.users];
  }

  openUserEditModal(user: any) {
    this.selectedUser = user;
    this.userEditRole = user.role;
    this.showUserEditModal = true;
  }

  saveUserRole() {
    if (!this.selectedUser) return;
    this.adminService.updateUserRole(this.selectedUser.id, this.userEditRole).subscribe({
      next: () => { this.statusMsg = '✅ Role updated'; this.showUserEditModal = false; this.loadUsers(); },
      error: err => this.statusMsg = '❌ ' + (err.error?.message || 'Error')
    });
  }

  toggleUserStatus(user: any) {
    const action = user.isActive ? 'deactivate' : 'activate';
    if (!confirm(`${action} user "${user.fullName || user.email}"?`)) return;
    this.adminService.updateUserStatus(user.id, !user.isActive).subscribe({
      next: () => { this.statusMsg = `✅ User ${action}d`; this.loadUsers(); },
      error: err => this.statusMsg = '❌ ' + (err.error?.message || 'Error')
    });
  }

  deleteUser(user: any) {
    if (!confirm(`Permanently delete user "${user.fullName || user.email}"? This cannot be undone.`)) return;
    this.adminService.deleteUser(user.id).subscribe({
      next: () => { this.statusMsg = '✅ User deleted'; this.loadUsers(); },
      error: err => this.statusMsg = '❌ ' + (err.error?.message || 'Error')
    });
  }

  formatDate(d: string): string {
    if (!d) return 'Never';
    return new Date(d).toLocaleDateString('en-IN', { day:'2-digit', month:'short', year:'numeric', hour:'2-digit', minute:'2-digit' });
  }

  getTimeAgo(d: string): string {
    if (!d) return 'Never';
    const diff = Date.now() - new Date(d).getTime();
    const h = Math.floor(diff / 3.6e6);
    const days = Math.floor(h / 24);
    if (h < 1) return 'Just now';
    if (h < 24) return `${h}h ago`;
    if (days < 7) return `${days}d ago`;
    return new Date(d).toLocaleDateString('en-IN');
  }

  // ── Leads ─────────────────────────────────────────────────────────────────

  loadLeads() {
    this.leadsLoading = true;
    this.adminService.getLeads(this.leadPage).subscribe({
      next: res => {
        this.leads = res.leads;
        this.leadTotal = res.total;
        this.filteredLeads = res.leads;
        this.leadsLoading = false;
      },
      error: () => { this.leadsLoading = false; }
    });
  }

  searchLeads() {
    const q = this.leadsSearchQuery.toLowerCase();
    this.filteredLeads = q
      ? this.leads.filter(l =>
          (l.name || '').toLowerCase().includes(q) ||
          (l.email || '').toLowerCase().includes(q) ||
          (l.mobile || '').toLowerCase().includes(q) ||
          (l.areaOfInterest || '').toLowerCase().includes(q) ||
          (l.projectName || '').toLowerCase().includes(q))
      : [...this.leads];
  }

  deleteLead(lead: any) {
    if (!confirm(`Delete lead from "${lead.name}" (${lead.email})?`)) return;
    this.leadsLoading = true;
    this.adminService.deleteLead(lead.id).subscribe({
      next: () => { this.statusMsg = '✅ Lead deleted'; this.loadLeads(); },
      error: err => { this.statusMsg = '❌ Error deleting lead'; this.leadsLoading = false; }
    });
  }

  // ── Visits ─────────────────────────────────────────────────────────────────

  loadVisits() {
    this.visitsLoading = true;
    this.adminService.getVisits().subscribe({
      next: (res: any[]) => {
        this.visits = res;
        this.filteredVisits = res;
        this.visitsLoading = false;
      },
      error: () => { this.visitsLoading = false; }
    });
  }

  searchVisits() {
    const q = this.visitsSearchQuery.toLowerCase();
    this.filteredVisits = q
      ? this.visits.filter(v =>
          (v.name || '').toLowerCase().includes(q) ||
          (v.email || '').toLowerCase().includes(q) ||
          (v.mobile || '').toLowerCase().includes(q) ||
          (v.projectName || '').toLowerCase().includes(q) ||
          (v.locationAddress || '').toLowerCase().includes(q))
      : [...this.visits];
  }

  updateVisitStatus(visit: any, status: string) {
    this.adminService.updateVisitStatus(visit.id, status).subscribe({
      next: () => {
        visit.status = status;
        this.statusMsg = `✅ Visit #${visit.id} marked as ${status}`;
      },
      error: () => { this.statusMsg = '❌ Error updating status'; }
    });
  }

  deleteVisit(visit: any) {
    if (!confirm(`Delete visit request from "${visit.name}"?`)) return;
    this.adminService.deleteVisit(visit.id).subscribe({
      next: () => { this.statusMsg = '✅ Visit deleted'; this.loadVisits(); },
      error: () => { this.statusMsg = '❌ Error deleting visit'; }
    });
  }

  getVisitStatusClass(status: string): string {
    if (status === 'confirmed') return 'visit-status-confirmed';
    if (status === 'cancelled') return 'visit-status-cancelled';
    return 'visit-status-pending';
  }

  // ── Scraper ────────────────────────────────────────────────────────────────

  loadPreferences() {
    this.propertyService.getScrapePreferences().subscribe({
      next: prefs => this.preferences = { pincodes: prefs.pincodes || [], igrs_username: prefs.igrs_username || '', igrs_password: prefs.igrs_password || '' },
      error: () => {}
    });
  }

  addPincode() {
    const v = this.newPincode.trim();
    if (v && !this.preferences.pincodes.includes(v)) this.preferences.pincodes.push(v);
    this.newPincode = '';
    this.prefsSaved = false;
  }

  removePincode(i: number) { this.preferences.pincodes.splice(i, 1); this.prefsSaved = false; }

  savePreferences() {
    this.prefsLoading = true;
    this.propertyService.saveScrapePreferences(this.preferences).subscribe({
      next: () => { this.prefsLoading = false; this.prefsSaved = true; this.statusMsg = `✅ Preferences saved (${this.preferences.pincodes.length} pincodes).`; },
      error: () => { this.prefsLoading = false; this.statusMsg = '❌ Could not save. Is the Python backend running?'; }
    });
  }

  pollRrStatus() {
    this.propertyService.getRrScrapeStatus().subscribe({ next: s => this.rrScrapeStatus = s, error: () => {} });
  }

  startRrScrape() {
    if (!confirm('Start Ready Reckoner scraping for your saved pincodes?')) return;
    this.rrScrapeLoading = true;
    this.propertyService.startRrScrape(this.preferences.pincodes).subscribe({
      next: (res: any) => {
        this.rrScrapeLoading = false;
        this.rrScrapeStatus = { is_running: true, message: 'Starting…', total_records: 0 };
        this.statusMsg = res.message || 'RR scraping started';
        this._rrPoller = setInterval(() => {
          this.propertyService.getRrScrapeStatus().subscribe({
            next: (s: any) => { this.rrScrapeStatus = s; if (!s?.is_running) clearInterval(this._rrPoller); },
            error: () => {}
          });
        }, 5000);
      },
      error: (e: any) => { this.rrScrapeLoading = false; this.statusMsg = '❌ ' + (e?.error?.message || 'Could not start RR scraper'); }
    });
  }

  stopRrScrape() {
    this.propertyService.stopRrScrape().subscribe({ next: () => this.statusMsg = 'Stop requested', error: () => {} });
  }

  pollSroStatus() {
    this.propertyService.getSroScrapeStatus().subscribe({ next: s => this.sroScrapeStatus = s, error: () => {} });
  }

  startSroScrape() {
    if (!confirm('Start SRO transaction scraping? This may take 20-40 minutes.')) return;
    this.sroScrapeLoading = true;
    this.propertyService.startSroScrape({ start_year: 2021 }).subscribe({
      next: (res: any) => {
        this.sroScrapeLoading = false;
        this.sroScrapeStatus = { is_running: true, message: 'Starting…', total_records: 0 };
        this.statusMsg = res.message || 'SRO scraping started';
        this._sroPoller = setInterval(() => {
          this.propertyService.getSroScrapeStatus().subscribe({
            next: (s: any) => { this.sroScrapeStatus = s; if (!s?.is_running) clearInterval(this._sroPoller); },
            error: () => {}
          });
        }, 6000);
      },
      error: (e: any) => { this.sroScrapeLoading = false; this.statusMsg = '❌ ' + (e?.error?.message || 'Could not start SRO scraper'); }
    });
  }

  bulkScrape() {
    if (!confirm('Start bulk RERA scrape? This runs in the background.')) return;
    this.loading = true;
    this.statusMsg = 'Starting RERA scraper...';
    this.propertyService.bulkScrape().subscribe({
      next: res => { this.statusMsg = res.message || 'Bulk scraping started'; this.loading = false; },
      error: err => { this.statusMsg = '❌ ' + (err.error?.message || 'Error'); this.loading = false; }
    });
  }

  fetchProjectNames() {
    this.loading = true;
    this.statusMsg = 'Fetching project names...';
    this.propertyService.fetchProjectNames().subscribe({
      next: res => { this.statusMsg = res.message || 'Done'; this.loading = false; setTimeout(() => this.loadProperties(), 1000); },
      error: err => { this.statusMsg = '❌ ' + (err.error?.message || 'Error'); this.loading = false; }
    });
  }

  // ── Media ─────────────────────────────────────────────────────────────────

  openMediaModal(property: any) {
    this.selectedProperty = property;
    this.mediaTab = 'image';
    this.uploadQueue = [];
    this.videoUrl = '';
    this.videoTitle = '';
    this.editingMediaId = null;
    this.showMediaModal = true;
    const id = property.id || property.projectId;
    this.loadMedia(id);
    this.loadScrapedFloorPlans(id);
  }

  loadMedia(projectId: string) {
    this.mediaLoading = true;
    this.mediaService.getMedia(projectId).subscribe({
      next: items => { this.allMedia = items; this.mediaLoading = false; },
      error: () => this.mediaLoading = false
    });
  }

  loadScrapedFloorPlans(projectId: string) {
    this.scrapedLoading = true;
    this.propertyService.getFloorPlans(projectId).subscribe({
      next: entries => { this.scrapedFloorPlans = entries || []; this.scrapedLoading = false; },
      error: () => { this.scrapedFloorPlans = []; this.scrapedLoading = false; }
    });
  }

  /** Returns total number of scraped pages across all docs */
  get scrapedPageCount(): number {
    return this.scrapedFloorPlans.reduce((sum, e) => sum + (e.pages?.length || 0), 0);
  }

  /** Extract just the filename from a page URL like /api/projects/{id}/floor-plans/{filename} */
  scrapedFilename(pageUrl: string): string {
    return pageUrl.split('/').pop() || pageUrl;
  }

  promoteScrapedPage(pageUrl: string, docName: string) {
    if (!this.selectedProperty) return;
    const id = this.selectedProperty.id || this.selectedProperty.projectId;
    const filename = this.scrapedFilename(pageUrl);
    this.promotingPage = filename;
    this.mediaService.registerScrapedPage(id, pageUrl, docName).subscribe({
      next: () => { this.promotingPage = null; this.loadMedia(id); this.statusMsg = '✅ Added to floor plans'; },
      error: () => { this.promotingPage = null; this.statusMsg = '❌ Failed to register'; }
    });
  }

  deleteScrapedPage(pageUrl: string) {
    const filename = this.scrapedFilename(pageUrl);
    if (!confirm(`Delete scraped page "${filename}"? This removes it from disk.`)) return;
    if (!this.selectedProperty) return;
    const id = this.selectedProperty.id || this.selectedProperty.projectId;
    this.propertyService.deleteScrapedFloorPlanPage(id, filename).subscribe({
      next: () => { this.statusMsg = '✅ Deleted'; this.loadScrapedFloorPlans(id); },
      error: () => { this.statusMsg = '❌ Error deleting'; }
    });
  }

  getMediaByType(type: string): any[] {
    return this.allMedia.filter((m: any) => (m.mediaType || m.media_type) === type);
  }

  getAcceptTypes(): string {
    if (this.mediaTab === 'document') return '.pdf,.doc,.docx';
    return '.jpg,.jpeg,.png,.webp,.gif';
  }

  onFilesSelected(event: any) {
    const files: FileList = event.target.files;
    this.uploadQueue = Array.from(files);
    event.target.value = '';
  }

  removeFromQueue(i: number) { this.uploadQueue.splice(i, 1); }

  uploadFiles() {
    if (!this.selectedProperty || this.uploadQueue.length === 0) return;
    const id = this.selectedProperty.id || this.selectedProperty.projectId;
    this.uploading = true;
    let completed = 0;
    this.uploadQueue.forEach(file => {
      this.mediaService.uploadFile(id, file, this.mediaTab, file.name.replace(/\.[^.]+$/, '')).subscribe({
        next: () => {
          completed++;
          if (completed === this.uploadQueue.length) {
            this.uploading = false;
            this.uploadQueue = [];
            this.statusMsg = `✅ ${completed} file(s) uploaded`;
            this.loadMedia(id);
          }
        },
        error: err => {
          this.uploading = false;
          this.statusMsg = '❌ Upload error: ' + (err.error?.message || 'Unknown');
        }
      });
    });
  }

  addVideoUrl() {
    if (!this.selectedProperty || !this.videoUrl) return;
    const id = this.selectedProperty.id || this.selectedProperty.projectId;
    this.uploading = true;
    this.mediaService.addVideo(id, this.videoUrl, this.videoTitle).subscribe({
      next: () => {
        this.uploading = false;
        this.videoUrl = '';
        this.videoTitle = '';
        this.statusMsg = '✅ Video added';
        this.loadMedia(id);
      },
      error: err => { this.uploading = false; this.statusMsg = '❌ ' + (err.error?.message || 'Error'); }
    });
  }

  addImageByUrl() {
    const url = this.imageUrlInput.trim();
    if (!url || !this.selectedProperty) return;
    const id = this.selectedProperty.id || this.selectedProperty.projectId;
    this.uploading = true;
    this.mediaService.registerScrapedPage(id, url, this.imageUrlTitle || undefined, this.mediaTab).subscribe({
      next: () => {
        this.uploading = false;
        this.imageUrlInput = '';
        this.imageUrlTitle = '';
        this.statusMsg = '✅ Image URL registered';
        this.loadMedia(id);
      },
      error: err => { this.uploading = false; this.statusMsg = '❌ ' + (err.error?.message || 'Error'); }
    });
  }

  startEditMedia(m: any) {
    this.editingMediaId = m.id;
    this.editingMediaTitle = m.title || m.fileName || m.file_name || '';
  }

  saveMediaEdit(m: any) {
    if (!this.selectedProperty) return;
    const pid = this.selectedProperty.id || this.selectedProperty.projectId;
    this.mediaService.updateMedia(pid, m.id, this.editingMediaTitle, m.sortOrder || m.sort_order || 0).subscribe({
      next: () => { this.editingMediaId = null; this.loadMedia(pid); },
      error: () => this.editingMediaId = null
    });
  }

  deleteMediaItem(m: any) {
    if (!confirm(`Delete "${m.title}"?`)) return;
    if (!this.selectedProperty) return;
    const pid = this.selectedProperty.id || this.selectedProperty.projectId;
    this.mediaService.deleteMedia(pid, m.id).subscribe({
      next: () => { this.statusMsg = '✅ Deleted'; this.loadMedia(pid); },
      error: () => this.statusMsg = '❌ Error deleting media'
    });
  }

  getYTThumb(url: string): string { return this.mediaService.getYouTubeThumbnail(url); }

  onImgError(e: any) { e.target.style.display = 'none'; }

  formatFileSize(bytes: number): string {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / 1048576).toFixed(1) + ' MB';
  }

  closeModal() {
    this.showEditModal = false;
    this.showPricingModal = false;
    this.showCreateModal = false;
    this.showUserEditModal = false;
    this.showMediaModal = false;
    this.selectedProperty = null;
    this.selectedUser = null;
    this.uploadQueue = [];
    this.videoUrl = '';
    this.editingMediaId = null;
  }

  getStatusClass(s: string): string {
    if (!s) return 'badge-unknown';
    const sl = s.toLowerCase();
    if (sl.includes('completed')) return 'badge-completed';
    if (sl.includes('ongoing'))   return 'badge-ongoing';
    if (sl.includes('new'))       return 'badge-new';
    if (sl.includes('lapsed'))    return 'badge-lapsed';
    return 'badge-unknown';
  }

  getSectionTitle(): string {
    const titles: Record<string, string> = {
      dashboard:  'Dashboard',
      properties: 'Properties',
      users:      'Users',
      leads:      'Leads',
      visits:     'Site Visits',
      scraper:    'Scraper Control',
      social:     'Social Feed',
      resale:     'Resale Listings',
      reviews:    'Reviews'
    };
    return titles[this.activeSection] ?? 'Admin';
  }

  formatArea(area: any): string {
    if (!area) return 'N/A';
    const n = parseFloat(area);
    if (isNaN(n)) return area;
    return n.toLocaleString('en-IN', { maximumFractionDigits: 0 }) + ' sqm';
  }

  // ── Social Tweets ──────────────────────────────────────────────────────────

  loadTweets(): void {
    this.tweetsLoading = true;
    this.tweetsError = '';
    this.http.get<any[]>('/api/twitter/admin/tweets').subscribe({
      next: tweets => { this.tweets = tweets; this.tweetsLoading = false; },
      error: () => { this.tweetsError = 'Failed to load tweets.'; this.tweetsLoading = false; }
    });
  }

  addTweet(): void {
    const url = this.newTweetUrl.trim();
    if (!url) return;
    this.addingTweet = true;
    this.addTweetError = '';
    this.addTweetSuccess = '';
    this.http.post<any>('/api/twitter/admin/tweets', {
      url,
      label: this.newTweetLabel.trim() || null,
      isActive: true,
      sortOrder: 0
    }).subscribe({
      next: () => {
        this.addTweetSuccess = 'Tweet added successfully.';
        this.newTweetUrl = '';
        this.newTweetLabel = '';
        this.addingTweet = false;
        this.loadTweets();
        setTimeout(() => this.addTweetSuccess = '', 3000);
      },
      error: err => {
        this.addTweetError = err.error?.error || 'Failed to add tweet.';
        this.addingTweet = false;
      }
    });
  }

  toggleTweet(id: string): void {
    this.http.post<any>(`/api/twitter/admin/tweets/${id}/toggle`, {}).subscribe({
      next: updated => {
        const idx = this.tweets.findIndex(t => t.id === id);
        if (idx > -1) this.tweets[idx] = updated;
      },
      error: () => { this.statusMsg = '❌ Failed to toggle tweet'; }
    });
  }

  deleteTweet(id: string, url: string): void {
    if (!confirm(`Remove tweet?\n${url}`)) return;
    this.http.delete(`/api/twitter/admin/tweets/${id}`).subscribe({
      next: () => {
        this.tweets = this.tweets.filter(t => t.id !== id);
        this.statusMsg = '✅ Tweet removed';
        setTimeout(() => this.statusMsg = '', 3000);
      },
      error: () => { this.statusMsg = '❌ Failed to delete tweet'; }
    });
  }

  // ── Resale listings ───────────────────────────────────────────────────────

  loadResaleListings(): void {
    this.resaleLoading = true;
    const status = this.resaleFilter !== 'all' ? `?status=${this.resaleFilter}` : '';
    this.http.get<any>(`/api/admin/resale${status}`).subscribe({
      next: res => { this.resaleListings = res.listings || []; this.resaleLoading = false; },
      error: () => { this.resaleLoading = false; this.statusMsg = '❌ Failed to load resale listings'; }
    });
  }

  get filteredResale(): any[] {
    if (!this.resaleSearch.trim()) return this.resaleListings;
    const q = this.resaleSearch.toLowerCase();
    return this.resaleListings.filter(l =>
      (l.owner_name || '').toLowerCase().includes(q) ||
      (l.project_name || '').toLowerCase().includes(q) ||
      (l.location || '').toLowerCase().includes(q) ||
      (l.contact_phone || '').toLowerCase().includes(q) ||
      (l.configuration || '').toLowerCase().includes(q)
    );
  }

  updateResaleStatus(id: string, status: string, adminNotes?: string): void {
    this.resaleUpdating = id;
    this.http.put(`/api/admin/resale/${id}/status`, { status, adminNotes: adminNotes || null }).subscribe({
      next: () => {
        const listing = this.resaleListings.find(l => l.id === id);
        if (listing) listing.status = status;
        this.resaleUpdating = null;
        this.statusMsg = `✅ Listing marked as ${status}`;
        setTimeout(() => this.statusMsg = '', 3000);
      },
      error: () => { this.resaleUpdating = null; this.statusMsg = '❌ Failed to update status'; }
    });
  }

  getResaleImages(listing: any): string[] {
    try {
      const imgs = typeof listing.images === 'string' ? JSON.parse(listing.images) : listing.images;
      return Array.isArray(imgs) ? imgs : [];
    } catch { return []; }
  }

  getResaleFeatures(listing: any): string[] {
    try {
      const f = typeof listing.features === 'string' ? JSON.parse(listing.features) : listing.features;
      return Array.isArray(f) ? f : [];
    } catch { return []; }
  }

  formatResalePrice(v: number): string {
    if (!v) return '—';
    if (v >= 10000000) return `₹${(v / 10000000).toFixed(2)} Cr`;
    if (v >= 100000)   return `₹${(v / 100000).toFixed(2)} L`;
    return `₹${v.toLocaleString('en-IN')}`;
  }

  resaleStatusClass(s: string): string {
    const m: Record<string, string> = { pending: 'badge-pending', active: 'badge-active', sold: 'badge-sold', rejected: 'badge-rejected' };
    return m[s] || 'badge-pending';
  }

  // ── Reviews ───────────────────────────────────────────────────────────────

  loadReviews(): void {
    this.reviewsLoading = true;
    this.adminService.getReviews().subscribe({
      next: (reviews) => { this.adminReviews = reviews; this.reviewsLoading = false; },
      error: () => { this.reviewsLoading = false; this.statusMsg = '❌ Failed to load reviews'; }
    });
  }

  get filteredAdminReviews(): any[] {
    let list = this.adminReviews;
    if (this.reviewsFilter === 'pending')  list = list.filter(r => !r.isApproved);
    if (this.reviewsFilter === 'approved') list = list.filter(r =>  r.isApproved);
    const q = this.reviewsSearch.trim().toLowerCase();
    if (q) list = list.filter(r =>
      (r.name || '').toLowerCase().includes(q) ||
      (r.projectId || '').toLowerCase().includes(q) ||
      (r.review || '').toLowerCase().includes(q)
    );
    return list;
  }

  get pendingReviewCount(): number {
    return this.adminReviews.filter(r => !r.isApproved).length;
  }

  get approvedReviewCount(): number {
    return this.adminReviews.filter(r => r.isApproved).length;
  }

  approveAdminReview(review: any): void {
    this.adminService.approveReview(review.id).subscribe({
      next: () => {
        review.isApproved = true;
        this.statusMsg = `✅ Review by "${review.name}" approved`;
        setTimeout(() => this.statusMsg = '', 3000);
      },
      error: () => { this.statusMsg = '❌ Failed to approve review'; }
    });
  }

  deleteAdminReview(review: any): void {
    if (!confirm(`Delete review by "${review.name}"?`)) return;
    this.adminService.deleteReview(review.id).subscribe({
      next: () => {
        this.adminReviews = this.adminReviews.filter(r => r.id !== review.id);
        this.statusMsg = `🗑 Review deleted`;
        setTimeout(() => this.statusMsg = '', 3000);
      },
      error: () => { this.statusMsg = '❌ Failed to delete review'; }
    });
  }
}
