@echo off
setlocal
set SCRIPT_DIR=%~dp0
set STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
set SHORTCUT=%STARTUP_DIR%\Command Center Backend.lnk

REM Point a Startup shortcut at the committed backend-only launcher so the
REM backend starts silently on every Windows login.
powershell -NoProfile -Command "$s = (New-Object -ComObject WScript.Shell).CreateShortcut('%SHORTCUT%'); $s.TargetPath='%SCRIPT_DIR%_backend_only.bat'; $s.WorkingDirectory='%SCRIPT_DIR%'; $s.WindowStyle=7; $s.Description='Command Center backend (auto-start)'; $s.Save()"

echo Auto-start installed: backend will run on every Windows login.
echo To remove: run uninstall_autostart.bat (or delete "%SHORTCUT%").
pause
