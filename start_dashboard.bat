@echo off
cd /d "%~dp0"
echo Building React frontend...
cd frontend
call npm run build
cd ..
echo Starting Command Center...
start "" "http://localhost:8000"
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
