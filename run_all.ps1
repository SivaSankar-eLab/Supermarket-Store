# SupermarketBot PowerShell Launcher
Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host "       SUPERMARKETBOT - AI-POWERED STORE OPERATIONS AGENT" -ForegroundColor Cyan
Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Start Postgres if needed
$pgBin = ".\pgsql\bin\pg_ctl.exe"
if (Test-Path $pgBin) {
    & $pgBin status -D .\pgdata | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Starting PostgreSQL database..." -ForegroundColor Yellow
        & $pgBin start -D .\pgdata -l .\pgdata\postgres.log -w | Out-Null
    }
}

# 2. Run runner
python run_all.py
