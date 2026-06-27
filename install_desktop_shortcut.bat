@echo off
setlocal
set SCRIPT_DIR=%~dp0
set DESKTOP=%USERPROFILE%\Desktop
set SHORTCUT=%DESKTOP%\Personal Command Center v3.lnk

REM Target the silent .vbs launcher via wscript.exe so NO console/command
REM windows pop up (a .bat-targeted shortcut flashes a console and spawns
REM visible powershell children). The .vbs does a hidden health check, starts
REM the backend windowless (pythonw, output redirected to a log), waits until
REM healthy, then opens the browser at the Portfolio Hub (/portfolio).
REM Icon = the v3 crosshair brand mark (assets\icon.ico).
powershell -NoProfile -Command "$s = (New-Object -ComObject WScript.Shell).CreateShortcut('%SHORTCUT%'); $s.TargetPath='%WINDIR%\System32\wscript.exe'; $s.Arguments='\"%SCRIPT_DIR%launch_command_center.vbs\"'; $s.WorkingDirectory='%SCRIPT_DIR%'; $s.WindowStyle=7; $s.Description='Personal Command Center v3 - start dashboard and open the Portfolio Hub (no console windows)'; $s.IconLocation='%SCRIPT_DIR%assets\icon.ico,0'; $s.Save()"

REM Remove stale older shortcuts so the Desktop has one current launcher.
if exist "%DESKTOP%\Command Center.lnk" del "%DESKTOP%\Command Center.lnk"
if exist "%DESKTOP%\Command Center v2.lnk" del "%DESKTOP%\Command Center v2.lnk"

echo Desktop shortcut created: "%SHORTCUT%"
echo Double-click it to launch the dashboard at the Portfolio Hub (no popup windows).
pause
