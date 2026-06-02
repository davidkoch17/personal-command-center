@echo off
setlocal EnableDelayedExpansion

REM Move to project root
cd /d "%~dp0"

echo [Command Center] Pre-flight checks...

REM 1. Check if backend is alive
powershell -NoProfile -Command "$ok = $false; try { $r = Invoke-WebRequest -Uri 'http://localhost:8000/health' -UseBasicParsing -TimeoutSec 2; if ($r.StatusCode -eq 200) { $ok = $true } } catch {}; if ($ok) { exit 0 } else { exit 1 }"
if %errorlevel% equ 0 (
    echo [Command Center] Backend already running on port 8000.
    set BACKEND_NEW=0
) else (
    echo [Command Center] Backend not running — starting it now.
    set BACKEND_NEW=1
)

REM 2. Check if frontend build is stale
powershell -NoProfile -Command "$dist = 'frontend\dist\index.html'; $src = Get-ChildItem -Path 'frontend\src' -Recurse -File | Sort-Object LastWriteTime -Descending | Select-Object -First 1; if (-not (Test-Path $dist)) { exit 1 }; if ($src.LastWriteTime -gt (Get-Item $dist).LastWriteTime) { exit 1 } else { exit 0 }"
if %errorlevel% neq 0 (
    echo [Command Center] Frontend build stale — rebuilding...
    cd frontend
    call npm run build
    cd ..
) else (
    echo [Command Center] Frontend build is fresh.
)

REM 3. Start backend if not already running
if %BACKEND_NEW% equ 1 (
    echo [Command Center] Starting backend on port 8000...
    start "" /B pythonw -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
    REM Wait for backend to come up
    timeout /t 3 /nobreak >nul
)

REM 4. Open browser
echo [Command Center] Opening browser...
start "" "http://localhost:8000"

REM 5. Wait briefly so user sees status, then exit
timeout /t 2 /nobreak >nul
exit
