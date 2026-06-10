@echo off
setlocal
set SCRIPT_DIR=%~dp0
set DESKTOP=%USERPROFILE%\Desktop
set SHORTCUT=%DESKTOP%\Command Center v2.lnk

REM Target the silent .vbs launcher via wscript.exe so NO console/command
REM windows pop up (the old smart_launch.bat shortcut flashed a console and
REM spawned visible powershell children). The .vbs does a hidden health
REM check, starts the backend windowless, then opens the browser.
powershell -NoProfile -Command "$s = (New-Object -ComObject WScript.Shell).CreateShortcut('%SHORTCUT%'); $s.TargetPath='%WINDIR%\System32\wscript.exe'; $s.Arguments='\"%SCRIPT_DIR%launch_command_center.vbs\"'; $s.WorkingDirectory='%SCRIPT_DIR%'; $s.WindowStyle=7; $s.Description='Command Center v2 - start dashboard and open browser (no console windows)'; $s.IconLocation='%SCRIPT_DIR%assets\icon.ico,0'; $s.Save()"

REM Remove the stale pre-v2 shortcut if it is still around.
if exist "%DESKTOP%\Command Center.lnk" del "%DESKTOP%\Command Center.lnk"

echo Desktop shortcut created: "%SHORTCUT%"
echo Double-click it to launch the dashboard (no popup windows).
pause
