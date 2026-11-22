# Project Amaanat - Turnkey Offline Demo Launcher
# PROTOTYPE ONLY - Hackathon Demonstration Environment
# Sourced from docs/BLUEPRINT.md and AGENTS.md

Write-Host "==================================================================" -ForegroundColor Green
Write-Host " Project Amaanat (امانت) - Offline Demonstration Launcher" -ForegroundColor Green
Write-Host " PROTOTYPE ONLY - Not an official government service" -ForegroundColor Yellow
Write-Host " Pure Synthetic Data - 60s Reversible Hold - Fail-Closed Safety" -ForegroundColor Cyan
Write-Host "==================================================================" -ForegroundColor Green

$Root = Resolve-Path "$PSScriptRoot\.."
$VenvPython = "$Root\venv\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Host "Error: Virtual environment python not found at $VenvPython" -ForegroundColor Red
    exit 1
}

# 1. Environment configuration
$env:DATABASE_URL = "sqlite+aiosqlite:///$Root/demo.db"
$env:HOLD_DURATION_SECONDS = "60"
$env:TESTING = "0"
$env:IS_PROTOTYPE = "true"
$env:JWT_SECRET = "amaanat-demo-secret-key-hackathon-2026"
$env:DECISION_TOKEN_SECRET = "amaanat-capability-decision-token-demo-2026"
$env:MOCK_SERVICES_URL = "http://127.0.0.1:8001"

# 2. Database Initialization & Seeding
Write-Host "Initializing SQLite database and seeding base tenants & users..." -ForegroundColor Cyan
& $VenvPython -m api.seed

# 3. Start Mock Rails Service (Port 8001)
Write-Host "Starting Mock Services (NADRA, Raast, Telco) on http://127.0.0.1:8001..." -ForegroundColor Cyan
$MockJob = Start-Process -FilePath $VenvPython -ArgumentList "-m uvicorn mocks.main:app --port 8001 --host 127.0.0.1" -WorkingDirectory $Root -PassThru

Start-Sleep -Seconds 2

# 4. Start FastAPI Backend (Port 8000)
Write-Host "Starting FastAPI Backend API on http://127.0.0.1:8000..." -ForegroundColor Cyan
$ApiJob = Start-Process -FilePath $VenvPython -ArgumentList "-m uvicorn api.main:app --port 8000 --host 127.0.0.1" -WorkingDirectory $Root -PassThru

Start-Sleep -Seconds 3

# 5. Seed Demonstration Scenarios
Write-Host "Seeding live evaluation scenarios into demo database..." -ForegroundColor Cyan
try {
    & $VenvPython "$Root\scripts\seed_demo.py"
} catch {
    Write-Host "Warning: Could not seed scenarios immediately. Backend will warm up shortly." -ForegroundColor Yellow
}

# 6. Start Vite Frontend (Port 3000)
Write-Host "Starting React + TypeScript Web Frontend on http://localhost:3000..." -ForegroundColor Cyan
$WebJob = Start-Process -FilePath "npm.cmd" -ArgumentList "run dev" -WorkingDirectory "$Root\web" -PassThru

Write-Host ""
Write-Host "==================================================================" -ForegroundColor Green
Write-Host "  Project Amaanat is LIVE for Demonstration:" -ForegroundColor Green
Write-Host "  - Frontend Portal:    http://localhost:3000" -ForegroundColor White
Write-Host "  - Backend API Docs:   http://127.0.0.1:8000/docs" -ForegroundColor White
Write-Host "  - Mock Rails Docs:    http://127.0.0.1:8001/docs" -ForegroundColor White
Write-Host ""
Write-Host "  Seeded Logins (Password: Demo@12345):" -ForegroundColor Yellow
Write-Host "   - Citizen:   citizen@prd.test" -ForegroundColor White
Write-Host "   - Helper:    helper@prd.test" -ForegroundColor White
Write-Host "   - Officer:   officer@prd.test" -ForegroundColor White
Write-Host "   - Admin:     admin@prd.test" -ForegroundColor White
Write-Host "   - Auditor:   auditor@prd.test" -ForegroundColor White
Write-Host ""
Write-Host "  Demo Scenarios Ready in Judge Console Tab:" -ForegroundColor Cyan
Write-Host "   1. Clean Case -> AUTO (60-sec reversible hold, zero wrong approvals)" -ForegroundColor White
Write-Host "   2. Account Title Mismatch -> HUMAN (flagged on Raast bank title)" -ForegroundColor White
Write-Host "   3. Blurry/Forged Card -> ASK / HUMAN (OpenCV blur gate / ELA forensics)" -ForegroundColor White
Write-Host "   4. Name Variant -> AUTO (Fuzzy transliteration Unicode token matching)" -ForegroundColor White
Write-Host "   5. Mock Outage -> WAITING_FOR_SERVICE (Fail-closed safely)" -ForegroundColor White
Write-Host "==================================================================" -ForegroundColor Green
Write-Host "Press Ctrl+C to terminate all services." -ForegroundColor Yellow

try {
    while ($true) {
        Start-Sleep -Seconds 2
        if ($MockJob.HasExited -or $ApiJob.HasExited -or $WebJob.HasExited) {
            break
        }
    }
}
finally {
    Write-Host "Terminating background demo servers..." -ForegroundColor Yellow
    Stop-Process -Id $MockJob.Id -ErrorAction SilentlyContinue
    Stop-Process -Id $ApiJob.Id -ErrorAction SilentlyContinue
    Stop-Process -Id $WebJob.Id -ErrorAction SilentlyContinue
    Write-Host "Demo shutdown complete." -ForegroundColor Green
}
