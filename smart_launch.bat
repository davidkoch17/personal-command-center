@echo off
setlocal EnableDelayedExpansion

REM Move to project root
cd /d "%~dp0"

echo [Command Center] Pre-flight checks...

REM 0. Resolve a usable pythonw.exe. PATH is unreliable on this machine (the
REM    PATH "python" is the broken Microsoft Store stub), so prefer the real
REM    per-user install under LOCALAPPDATA (newest version first), then fall
REM    back to whatever "where" finds.
set "PYW="
for /f "delims=" %%d in ('dir /b /ad /o-n "%LOCALAPPDATA%\Programs\Python\Python3*" 2^>nul') do (
    if not defined PYW if exist "%LOCALAPPDATA%\Programs\Python\%%d\pythonw.exe" set "PYW=%LOCALAPPDATA%\Programs\Python\%%d\pythonw.exe"
)
if not defined PYW for /f "delims=" %%i in ('where pythonw.exe 2^>nul') do if not defined PYW set "PYW=%%i"
if not defined PYW (
    echo [Command Center] ERROR: pythonw.exe not found. Install Python 3.12+ from python.org.
    pause
    exit /b 1
)
echo [Command Center] Interpreter: !PYW!

REM 1. Check if backend is alive
powershell -NoProfile -Command "try { $r = Invoke-WebRequest -Uri 'http://localhost:8000/health' -UseBasicParsing -TimeoutSec 2; if ($r.StatusCode -eq 200) { exit 0 } } catch {}; exit 1"
if %errorlevel% equ 0 (
    echo [Command Center] Backend already running on port 8000.
    set BACKEND_NEW=0
) else (
    echo [Command Center] Backend not running — will start it.
    set BACKEND_NEW=1
)

REM 2. Check if frontend build is stale
powershell -NoProfile -Command "$dist = 'frontend\dist\index.html'; if (-not (Test-Path $dist)) { exit 1 }; $src = Get-ChildItem -Path 'frontend\src' -Recurse -File | Sort-Object LastWriteTime -Descending | Select-Object -First 1; if ($src.LastWriteTime -gt (Get-Item $dist).LastWriteTime) { exit 1 } else { exit 0 }"
if %errorlevel% neq 0 (
    echo [Command Center] Frontend build stale — rebuilding...
    pushd frontend
    call npm run build
    popd
) else (
    echo [Command Center] Frontend build is fresh.
)

REM 3. Start backend if not already running
if %BACKEND_NEW% equ 1 (
    echo [Command Center] Starting backend on port 8000...
    REM Redirect output to a log file: a windowless pythonw process has no
    REM console, so uvicorn's logging needs valid handles or it dies on startup.
    start "" /B "!PYW!" -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 > "%TEMP%\command_center_backend.log" 2>&1
    echo [Command Center] Waiting for backend ^(cold start loads finance libs, can take ~30-50s^)...
    powershell -NoProfile -Command "for ($i=0; $i -lt 80; $i++) { try { $r = Invoke-WebRequest -Uri 'http://localhost:8000/health' -UseBasicParsing -TimeoutSec 2; if ($r.StatusCode -eq 200) { exit 0 } } catch {}; Start-Sleep -Milliseconds 750 }; exit 1"
    if !errorlevel! neq 0 (
        echo [Command Center] WARNING: backend did not respond in time. Log: "%TEMP%\command_center_backend.log"
    ) else (
        echo [Command Center] Backend ready.
    )
)

REM 4. Open browser
echo [Command Center] Opening browser...
start "" "http://localhost:8000"

REM 5. Brief pause so the user can read status, then exit
timeout /t 2 /nobreak >nul
exit /b
