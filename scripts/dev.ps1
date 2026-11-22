# Project Amaanat - Unified Local Development Server Runner
# Starts Mocks (port 8001), Backend API (port 8000), and Vite Web Frontend (port 3000)

Write-Host "==========================================================" -ForegroundColor Green
Write-Host " Project Amaanat (امانت) - Local Development Launcher" -ForegroundColor Green
Write-Host " PROTOTYPE ONLY - Hackathon Demonstration Environment" -ForegroundColor Yellow
Write-Host "==========================================================" -ForegroundColor Green

$Root = Resolve-Path "$PSScriptRoot\.."
$VenvPython = "$Root\venv\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Host "Error: Virtual environment python not found at $VenvPython" -ForegroundColor Red
    exit 1
}

Write-Host "Starting Mock Public Rails Services on http://127.0.0.1:8001..." -ForegroundColor Cyan
$MockJob = Start-Process -FilePath $VenvPython -ArgumentList "-m uvicorn mocks.main:app --port 8001 --host 127.0.0.1" -WorkingDirectory $Root -PassThru

Start-Sleep -Seconds 2

Write-Host "Starting FastAPI Backend Server on http://127.0.0.1:8000..." -ForegroundColor Cyan
$ApiJob = Start-Process -FilePath $VenvPython -ArgumentList "-m uvicorn api.main:app --port 8000 --host 127.0.0.1 --reload" -WorkingDirectory $Root -PassThru

Start-Sleep -Seconds 2

Write-Host "Starting React + Vite Web PWA on http://localhost:3000..." -ForegroundColor Cyan
$WebJob = Start-Process -FilePath "npm.cmd" -ArgumentList "run dev" -WorkingDirectory "$Root\web" -PassThru

Write-Host ""
Write-Host "All services started successfully:" -ForegroundColor Green
Write-Host " - Mocks:    http://127.0.0.1:8001/docs" -ForegroundColor White
Write-Host " - Backend:  http://127.0.0.1:8000/docs" -ForegroundColor White
Write-Host " - Frontend: http://localhost:3000" -ForegroundColor White
Write-Host ""
Write-Host "Press Ctrl+C or close this window to terminate all services." -ForegroundColor Yellow

try {
    while ($true) {
        Start-Sleep -Seconds 2
        if ($MockJob.HasExited -or $ApiJob.HasExited -or $WebJob.HasExited) {
            break
        }
    }
}
finally {
    Write-Host "Shutting down background processes..." -ForegroundColor Yellow
    Stop-Process -Id $MockJob.Id -ErrorAction SilentlyContinue
    Stop-Process -Id $ApiJob.Id -ErrorAction SilentlyContinue
    Stop-Process -Id $WebJob.Id -ErrorAction SilentlyContinue
    Write-Host "Shutdown complete." -ForegroundColor Green
}
