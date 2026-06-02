@echo off
setlocal
set SCRIPT_DIR=%~dp0
set STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
set SHORTCUT=%STARTUP_DIR%\Command Center Backend.lnk

REM Create a wrapper script that ONLY starts the backend (no browser open)
echo @echo off > "%SCRIPT_DIR%_backend_only.bat"
echo cd /d "%SCRIPT_DIR%" >> "%SCRIPT_DIR%_backend_only.bat"
echo start "" /B pythonw -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 >> "%SCRIPT_DIR%_backend_only.bat"
echo exit >> "%SCRIPT_DIR%_backend_only.bat"

powershell -NoProfile -Command "$s = (New-Object -ComObject WScript.Shell).CreateShortcut('%SHORTCUT%'); $s.TargetPath='%SCRIPT_DIR%_backend_only.bat'; $s.WorkingDirectory='%SCRIPT_DIR%'; $s.WindowStyle=7; $s.Description='Command Center backend (auto-start)'; $s.Save()"

echo Auto-start installed: backend will run on every Windows login.
echo To remove: delete "%SHORTCUT%"
pause
