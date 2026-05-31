@echo off
REM Runs the weekly Market Researcher agent. Target this file from Task Scheduler.
cd /d "%~dp0"
REM Prefer a project venv, then the py launcher (handles the broken Store-stub
REM `python` on this machine), then bare python as a last resort.
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m modules.agents.market_researcher
) else (
    py -3 -m modules.agents.market_researcher 2>NUL || python -m modules.agents.market_researcher
)
