@echo off
REM Phase A capture watcher — polls the OneDrive inbox folders every 60s and
REM ingests new iOS-Shortcut captures into data/captures.db.
cd /d "%~dp0"
python -m modules.captures.watcher
