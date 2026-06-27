@echo off
setlocal
set SCRIPT_DIR=%~dp0
set STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
set SHORTCUT=%STARTUP_DIR%\Command Center Backend.lnk

REM Point a Startup shortcut at the silent .vbs launcher (backendonly mode) so
REM the v3 backend starts windowless on every Windows login - no console flash.
REM "backendonly" starts the backend without opening a browser.
powershell -NoProfile -Command "$s = (New-Object -ComObject WScript.Shell).CreateShortcut('%SHORTCUT%'); $s.TargetPath='%WINDIR%\System32\wscript.exe'; $s.Arguments='\"%SCRIPT_DIR%launch_command_center.vbs\" backendonly'; $s.WorkingDirectory='%SCRIPT_DIR%'; $s.WindowStyle=7; $s.IconLocation='%SCRIPT_DIR%assets\icon.ico,0'; $s.Description='Personal Command Center v3 backend (auto-start on login, windowless)'; $s.Save()"

echo Auto-start installed: backend will run on every Windows login (windowless).
echo To remove: run uninstall_autostart.bat (or delete "%SHORTCUT%").
pause
