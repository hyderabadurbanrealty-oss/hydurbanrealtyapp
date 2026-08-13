# ── HydUrban Quick Start ──────────────────────────────────────────────────────
# Launches all services: Flask (scrapers), .NET API, Angular frontend
# Usage:  .\quick-start.ps1
# ─────────────────────────────────────────────────────────────────────────────

$ROOT = $PSScriptRoot
$DOTNET = "C:\Program Files\dotnet\dotnet.exe"

Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "  HydUrban — Starting all services" -ForegroundColor Cyan
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan

# ── Stop any existing processes ───────────────────────────────────────────────
Write-Host "`n[1/4] Stopping any running services..." -ForegroundColor Yellow
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
Get-Process dotnet -ErrorAction SilentlyContinue | Stop-Process -Force
Get-Process node   -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 2

# ── Verify PostgreSQL is running ──────────────────────────────────────────────
Write-Host "[2/4] Checking PostgreSQL..." -ForegroundColor Yellow
$pg = Get-Service -Name "postgresql*" -ErrorAction SilentlyContinue
if ($pg -and $pg.Status -eq "Running") {
    Write-Host "      ✓ PostgreSQL is running" -ForegroundColor Green
} else {
    Write-Host "      ⚠ PostgreSQL not running — attempting to start..." -ForegroundColor Yellow
    Start-Service -Name "postgresql*" -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 3
}

# ── Start Python Flask (scraper orchestration) ────────────────────────────────
Write-Host "[3/4] Starting Python Flask (port 5000)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit -Title 'Flask Backend' -Command `"Set-Location '$ROOT\backend'; python app.py`""
Start-Sleep -Seconds 3
Write-Host "      ✓ Flask started" -ForegroundColor Green

# ── Start .NET API ────────────────────────────────────────────────────────────
Write-Host "[4/4] Starting .NET API (port 5001)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit -Title '.NET API' -Command `"Set-Location '$ROOT\backend-dotnet'; & '$DOTNET' run --urls http://localhost:5001`""

# Wait and verify the .NET API comes up
Write-Host "      Waiting for .NET API to start..." -ForegroundColor Gray
$apiUp = $false
for ($i = 0; $i -lt 12; $i++) {
    Start-Sleep -Seconds 3
    try {
        $r = Invoke-WebRequest -Uri "http://localhost:5001/api/projects" -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
        if ($r.StatusCode -eq 200) {
            $data = $r.Content | ConvertFrom-Json
            Write-Host "      ✓ .NET API ready — $($data.Count) properties loaded from DB" -ForegroundColor Green
            $apiUp = $true
            break
        }
    } catch { }
    Write-Host "      ... waiting ($($($i+1)*3)s)" -ForegroundColor Gray
}

if (-not $apiUp) {
    Write-Host "      ⚠ API may still be starting — check the .NET window for errors" -ForegroundColor Yellow
}

# ── Start Angular Frontend ────────────────────────────────────────────────────
Write-Host ""
Write-Host "[5/5] Starting Angular frontend (port 4200)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit -Title 'Angular Frontend' -Command `"Set-Location '$ROOT\frontend'; npm start`""

# ── Summary ───────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Green
Write-Host "  All services started!" -ForegroundColor Green
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Green
Write-Host ""
Write-Host "  Frontend  →  http://localhost:4200" -ForegroundColor Cyan
Write-Host "  .NET API  →  http://localhost:5001" -ForegroundColor Cyan
Write-Host "  Flask     →  http://localhost:5000" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Wait ~15 seconds for Angular to compile, then open:" -ForegroundColor Gray
Write-Host "  http://localhost:4200" -ForegroundColor White
Write-Host ""

# Open browser after Angular warms up
Start-Sleep -Seconds 15
Start-Process "http://localhost:4200"
