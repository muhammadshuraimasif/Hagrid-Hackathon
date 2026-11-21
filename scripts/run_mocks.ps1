# scripts/run_mocks.ps1
# Runs Mock Public Rails Services (NADRA, Raast, Telco) for local demos.
# PROTOTYPE ONLY - Synthetic Data Only

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   Amaanat Hackathon Prototype - Mock Public Rails Services" -ForegroundColor Cyan
Write-Host "   PROTOTYPE ONLY - Synthetic Data Only" -ForegroundColor Yellow
Write-Host "   NADRA (Identity), Raast (Payments), Telco (SMS)" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

$VenvPython = ".\venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    $VenvPython = "python"
}

Write-Host "Starting Mock Services on http://127.0.0.1:8001..." -ForegroundColor Green
& $VenvPython -m uvicorn mocks.main:app --host 127.0.0.1 --port 8001 --reload
