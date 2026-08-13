# Hyderabad Urban Reality

A full-stack real estate intelligence platform for Hyderabad that aggregates live data from the **RERA (Real Estate Regulatory Authority)** portal and **SRO (Sub-Registrar Office)** transaction records. Features include interactive map-based property discovery, market intelligence dashboards, a lead capture system, an AI chatbot, and an admin panel — all powered by automated web scrapers and a multi-service backend architecture.

---

## 🧱 Architecture Overview

```
┌─────────────────────────────────────────────┐
│          Angular 16 Frontend (SPA)           │
│  Map · Properties · Market Intel · Admin     │
│  Chatbot · RERA Compliance · Comparison      │
└──────────┬──────────────────┬───────────────┘
           │ :5001/api        │ :5000/api
    ┌──────▼──────┐    ┌──────▼──────────┐
    │ ASP.NET 8   │    │  Python Flask   │
    │  REST API   │    │  Scraper API    │
    │  (primary)  │    │  (Selenium)     │
    └──────┬──────┘    └──────┬──────────┘
           │                  │
    ┌──────▼──────────────────▼──────────┐
    │           JSON File Storage         │
    │  scraped_projects/ · leads.json     │
    │  sro_transactions.json · unit_rates │
    └────────────────────────────────────┘
```

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+, Node.js 20+, .NET 8 SDK
- Google Chrome (for Selenium scrapers)
- Tesseract OCR installed and on PATH

### 1 — Clone & setup Python environment
```powershell
git clone https://github.com/your-org/HyderabadUrbanReality.git
cd HyderabadUrbanReality

python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
```

If you get an execution policy error:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### 2 — Start all services (VS Code)
Use the built-in VS Code task:
> **Terminal → Run Task → 🚀 Start All Services**

Or start each manually:

| Service | Command | Port |
|---|---|---|
| Python Flask | `cd backend && python app.py` | 5000 |
| .NET API | `cd backend-dotnet && dotnet run` | 5001 |
| Angular Dev | `cd frontend && npm start` | 4200 |

Open **http://localhost:4200**

---

## 🛠️ Technology Stack

| Layer | Technology |
|---|---|
| Frontend | Angular 16, TypeScript, Mapbox GL JS |
| Primary API | ASP.NET Core 8, C# |
| Scraper API | Python 3.11, Flask, Flask-CORS |
| Scraping | Selenium, BeautifulSoup4, Pytesseract |
| Storage | JSON flat files (`scraped_projects/`, `leads.json`) |
| CI | GitHub Actions (parallel build + bundle analysis) |

---

## 📂 Project Structure

```
HyderabadUrbanReality/
├── .github/
│   └── workflows/
│       ├── ci.yml               # CI — Angular + .NET + Python builds
│       └── bundle-analysis.yml  # Frontend bundle size report
├── backend/                     # Python Flask scraper API (:5000)
│   ├── app.py                   # Flask routes
│   ├── rera_detail_scraper.py   # RERA portal scraper (Selenium)
│   ├── sro_transaction_scraper.py # SRO transaction scraper
│   ├── rr_scraper.py            # Registration records scraper
│   ├── captcha_solver.py        # OCR-based CAPTCHA solver
│   ├── ProjectNameRetriever.py  # Fetches all RERA project names
│   └── scraped_projects/        # Output: per-project JSON + documents
│       ├── all_projects_data.json
│       ├── sro_transactions.json
│       └── unit_rates.json
├── backend-dotnet/              # ASP.NET Core 8 primary API (:5001)
│   ├── Controllers/
│   │   └── ProjectController.cs # All REST endpoints
│   ├── Core/
│   │   ├── Interfaces/          # IProjectService, IAuthService, etc.
│   │   └── DTOs/                # Request/response DTOs
│   ├── Application/Services/
│   │   └── ProjectService.cs
│   ├── Infrastructure/
│   │   ├── Repositories/        # ProjectRepository (JSON I/O)
│   │   └── Services/            # Auth, File, OpenStreetMap, InputSanitizer
│   ├── Models/                  # Lead.cs, ProjectData.cs
│   └── leads.json               # Captured leads (auto-created)
└── frontend/                    # Angular 16 SPA (:4200)
    └── src/app/
        ├── home/                # Landing page
        ├── map/                 # Interactive Mapbox map + lead capture
        ├── properties/          # Property listing & search
        ├── property-detail/     # Full project detail + unlock system
        ├── comparison/          # Side-by-side project comparison
        ├── market-intelligence/ # SRO transaction charts & price trends
        ├── neighborhood-intelligence/ # Child component (embedded in property-detail) — OSM amenity data
        ├── rera-compliance/     # Child component (embedded in property-detail) — compliance score
        ├── admin/               # Admin panel (lead management, scraper control)
        ├── chatbot/             # AI chatbot component
        ├── about/               # About page
        ├── login.component.ts   # Admin login
        ├── auth.interceptor.ts  # JWT auth interceptor
        └── services/            # PropertyService, SearchService, LoadingService
```

---

## 📋 Features

### Frontend (Angular)
- 🗺️ **Interactive Map** — Mapbox GL JS map embedded in the home page, showing all RERA project pins
- 🏠 **Property Listings** — Search and browse all scraped RERA-registered projects (`/properties`)
- 📊 **Property Detail** — Tabbed detail view (`/property/:id`) with: overview, RERA data, pricing, amenities, documents, and reviews tab (placeholder)
- 🏘️ **Neighborhood Intelligence** — Child component within property detail; fetches nearby amenities (schools, hospitals, transit) via OpenStreetMap Overpass API
- ⚖️ **RERA Compliance** — Child component within property detail; calculates a compliance score from scraped RERA fields (registration, timeline, fund utilization)
- ↔️ **Project Comparison** — Side-by-side compare projects with density metrics and price charts (`/comparison`)
- 📈 **Market Intelligence** — SRO transaction charts, city-wide and per-locality price/volume trends (`/market-intelligence`)
- 🤖 **Chatbot** — Floating chat overlay on all pages; rule-based assistant that searches and recommends properties based on user input
- 🔐 **Admin Panel** — JWT-protected panel (`/admin`); manage leads, edit projects, configure scrape pincodes, trigger RERA/SRO/RR scrapers
- 🔓 **Lead Capture** — Full project data is gated behind a lead form; submission unlocked via `submit_lead` + `check_unlock`

### .NET API Endpoints (`/api/...`)

| Endpoint | Method | Description |
|---|---|---|
| `projects` | GET | List all projects |
| `projects/{id}` | GET | Single project detail |
| `projects` | POST | Add new project |
| `projects/{id}` | DELETE | Remove project |
| `projects/{id}/pricing` | PUT | Update pricing |
| `projects/{id}/price-history` | GET | Price history |
| `projects/{id}/reviews` | GET | Project reviews (stub — returns empty array) |
| `projects/{id}/neighborhood-data` | GET | Nearby amenities via OpenStreetMap Overpass API |
| `submit_lead` | POST | Capture lead |
| `check_unlock` | GET | Check unlock status |
| `leads` | GET | List all leads (admin) |
| `leads/{index}` | DELETE | Delete a lead |
| `upload` | POST | File upload |
| `login` / `logout` | POST | Admin auth |
| `fetch_project_names` | POST | Trigger RERA name fetch |
| `scrape_project` | POST | Scrape single project |
| `bulk_scrape` | POST | Bulk scrape all projects |
| `scrape-preferences` | GET/POST | Scraper config |
| `sro/aggregate/city` | GET | City-wide transaction aggregates |
| `sro/aggregate/locality` | GET | Per-locality aggregates |
| `sro/rank/price` | GET | Locality price rankings |
| `sro/rank/volume` | GET | Locality volume rankings |
| `sro/project/trend` | GET | Project-level price trend |
| `sro/scrape` | POST | Trigger SRO scrape |
| `rr_scrape` | POST | Trigger RR scrape |
| `unit_rates` | GET | Unit rates data |
| `unit_rates/summary` | GET | Unit rates summary |
| `python/status` | GET | Python backend health |

### Python Flask API (`/api/...`)
Handles all Selenium-based scraping directly:
- **RERA project name retrieval** — fetches list from GIS portal, filtered by configured pincodes
- **RERA project detail scraping** — Selenium + BeautifulSoup; extracts all form fields and tables into `view_page_data.json`; records available document names (does **not** download files)
- **SRO transaction scraping** — collects apartment sale deed records; aggregates by quarter, locality, and city-wide
- **Ready Reckoner (RR) scraping** — fetches IGRS Telangana unit rates by pincode
- All scrapers run in background threads with a global mutex (only one scraper at a time) and expose status polling endpoints

> **Note on document handling:** The RERA scraper records the *names* of available documents from the detail page into `availableDocuments[]` in the JSON. It does **not** download the actual PDF/document files.

---

## 🔄 CI/CD (GitHub Actions)

### CI — [`ci.yml`](.github/workflows/ci.yml)
Triggers on every push to `master`/`main`/`develop` and on PRs to `master`/`main`.
Runs three **parallel** jobs:

| Job | Steps |
|---|---|
| Angular Frontend | `npm ci` → `npm run build:prod` → upload `dist/` artifact |
| Python Backend | `pip install` → `py_compile` syntax check on all modules |
| .NET Backend | `dotnet restore` → `dotnet build --Release` → `dotnet publish` → upload artifact |

### Bundle Analysis — [`bundle-analysis.yml`](.github/workflows/bundle-analysis.yml)
Triggers on push to `main` when frontend source changes, or manually.
Builds with `stats.json`, generates a `webpack-bundle-analyzer` HTML report, and uploads it as an artifact (retained 30 days).

---

## 🔧 Troubleshooting

### Virtual environment not activating
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
.\.venv\Scripts\Activate.ps1
```

### Python module not found after activating venv
Press `Ctrl+Shift+P` → **Developer: Reload Window** — VS Code needs to pick up the new interpreter.

### .NET build fails
```powershell
cd backend-dotnet
dotnet restore
dotnet build
```

### Selenium / Chrome errors
Ensure Google Chrome is installed and up to date. `webdriver-manager` handles the ChromeDriver download automatically.

### CAPTCHA solving fails
The OCR-based solver (`captcha_solver.py` using Pytesseract) can occasionally misread the CAPTCHA. Re-running the scrape usually resolves it.
#   h y d u r b a n r e a l t y  
 