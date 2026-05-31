@echo off
cd /d "%~dp0"
start "" "http://localhost:8501"
python -m streamlit run dashboard/Home.py --server.address 0.0.0.0
