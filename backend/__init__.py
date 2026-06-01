"""FastAPI backend package for the Personal Command Center.

Wraps the existing ``core`` / ``modules`` Python code as REST + WebSocket
endpoints for the React frontend (Phase 12). Streamlit keeps running in
parallel; both read the vault directly and share no in-process state.
"""
