#!/usr/bin/env pwsh
<#
.SYNOPSIS
    MyGameShelf — one-command launcher. Starts the FastAPI backend AND the
    Next.js frontend together so the backend is always reachable when you open
    the page.

.DESCRIPTION
    Run from anywhere:   .\start.ps1
    First run auto-creates the Python venv (.venv), installs backend deps, and
    runs `npm install` for the frontend if needed. Press Ctrl+C once to stop both.

.PARAMETER NoReload
    Disable uvicorn auto-reload (slightly faster, cleaner shutdown).
#>
param(
    [switch]$NoReload,
    [switch]$Open   # open http://localhost:3000 in the browser once started
)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
Set-Location $root

$venvPy = Join-Path $root ".venv\Scripts\python.exe"

# ── 1. Backend venv + dependencies ───────────────────────────────────────────
if (-not (Test-Path $venvPy)) {
    Write-Host "[setup] Creating Python venv (.venv) with CPython..." -ForegroundColor Cyan
    py -3.13 -m venv .venv
    & $venvPy -m pip install --upgrade pip --quiet
    Write-Host "[setup] Installing backend dependencies..." -ForegroundColor Cyan
    & $venvPy -m pip install -r requirements.txt
}

# ── 2. .env sanity check ─────────────────────────────────────────────────────
$envFile = Join-Path $root ".env"
if (-not (Test-Path $envFile)) {
    Write-Host "[warn] No .env found. Copy .env.example to .env and fill it in." -ForegroundColor Yellow
} elseif (-not (Select-String -Path $envFile -Pattern '^SUPABASE_JWT_SECRET=.+' -Quiet)) {
    Write-Host "[warn] SUPABASE_JWT_SECRET is empty in .env — login/data calls will return 500 until you set it." -ForegroundColor Yellow
}

# ── 3. Frontend dependencies ─────────────────────────────────────────────────
$webDir = Join-Path $root "web"
if (-not (Test-Path (Join-Path $webDir "node_modules"))) {
    Write-Host "[setup] Installing frontend dependencies (npm install)..." -ForegroundColor Cyan
    Push-Location $webDir
    npm install
    Pop-Location
}

# ── 4. Launch both processes in this console ─────────────────────────────────
$uvicornArgs = @("-m", "uvicorn", "api.main:app", "--port", "8000")
if (-not $NoReload) { $uvicornArgs += "--reload" }

$procs = @()
try {
    Write-Host "`n[run] FastAPI  -> http://localhost:8000" -ForegroundColor Green
    $procs += Start-Process -FilePath $venvPy -ArgumentList $uvicornArgs `
        -WorkingDirectory $root -NoNewWindow -PassThru

    Write-Host "[run] Sync worker (Steam job queue)" -ForegroundColor Green
    $procs += Start-Process -FilePath $venvPy -ArgumentList @("worker.py") `
        -WorkingDirectory $root -NoNewWindow -PassThru

    Write-Host "[run] Next.js  -> http://localhost:3000" -ForegroundColor Green
    # npm on Windows is a shell script, not a Win32 exe — go through cmd.exe so
    # Start-Process can launch it. Killing the cmd.exe tree (/T) stops node too.
    $procs += Start-Process -FilePath "cmd.exe" -ArgumentList @("/c", "npm", "run", "dev") `
        -WorkingDirectory $webDir -NoNewWindow -PassThru

    Write-Host "`nAll running. Open http://localhost:3000  —  press Ctrl+C to stop everything.`n" -ForegroundColor Cyan

    if ($Open) {
        Start-Job { Start-Sleep 6; Start-Process "http://localhost:3000" } | Out-Null
    }

    Wait-Process -Id $procs.Id
}
finally {
    Write-Host "`n[stop] Shutting down backend + frontend..." -ForegroundColor Yellow
    foreach ($p in $procs) {
        if ($p -and -not $p.HasExited) {
            # /T kills the whole tree (uvicorn --reload spawns a child reloader).
            cmd /c "taskkill /F /T /PID $($p.Id)" 2>$null | Out-Null
        }
    }
}
