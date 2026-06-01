@echo off
REM Archived Streamlit dashboard (Phases 1-10). Superseded by the React Cockpit
REM in Phase 14; kept for reference only. See _legacy/README.md.
cd /d "%~dp0"
start "" "http://localhost:8501"
python -m streamlit run _legacy/streamlit_dashboard/Home.py --server.address 0.0.0.0
