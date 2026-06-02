@echo off
setlocal
set SCRIPT_DIR=%~dp0
set DESKTOP=%USERPROFILE%\Desktop
set SHORTCUT=%DESKTOP%\Command Center.lnk

powershell -NoProfile -Command "$s = (New-Object -ComObject WScript.Shell).CreateShortcut('%SHORTCUT%'); $s.TargetPath='%SCRIPT_DIR%smart_launch.bat'; $s.WorkingDirectory='%SCRIPT_DIR%'; $s.WindowStyle=7; $s.Description='Launch David Command Center'; $s.IconLocation='%SCRIPT_DIR%assets\icon.ico,0'; $s.Save()"

echo Desktop shortcut created: "%SHORTCUT%"
echo Double-click it to launch the dashboard.
pause
