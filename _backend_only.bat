@echo off
setlocal EnableDelayedExpansion

REM Starts ONLY the backend (no browser). Used by the Windows auto-start
REM shortcut so the dashboard is warm on every login. Runs windowless.
cd /d "%~dp0"

REM Resolve a usable pythonw.exe (PATH is unreliable; prefer the real per-user
REM install under LOCALAPPDATA, newest first, then fall back to "where").
set "PYW="
for /f "delims=" %%d in ('dir /b /ad /o-n "%LOCALAPPDATA%\Programs\Python\Python3*" 2^>nul') do (
    if not defined PYW if exist "%LOCALAPPDATA%\Programs\Python\%%d\pythonw.exe" set "PYW=%LOCALAPPDATA%\Programs\Python\%%d\pythonw.exe"
)
if not defined PYW for /f "delims=" %%i in ('where pythonw.exe 2^>nul') do if not defined PYW set "PYW=%%i"
if not defined PYW exit /b 1

REM Redirect output so the windowless process keeps logging instead of dying.
start "" /B "!PYW!" -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 > "%TEMP%\command_center_backend.log" 2>&1
exit /b
