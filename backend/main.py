"""FastAPI backend for the Personal Command Center.

Run (development):
    uvicorn backend.main:app --reload --port 8000

Run (LAN, for iPad access during dev):
    python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
    (see ``start_backend.bat``)

All business logic lives in ``core`` / ``modules``; this layer only adapts it
to HTTP. Streamlit (port 8501) continues to work unchanged alongside this.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api import (
    tasks, projects, ideas, inbox, portfolio, money,
    watchlist, brand, career, integrations, runs,
    search, skills, reading, system,
)


app = FastAPI(
    title="Personal Command Center API",
    description="Backend for David's command center dashboard",
    version="1.0.0",
)

# CORS — localhost dev servers + Streamlit during the transition.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # Vite dev
        "http://localhost:3000",   # Next.js dev
        "http://localhost:8501",   # Streamlit during transition
    ],
    # Allow any LAN IP (iPad access) on common dev ports. Starlette applies
    # allow_origin_regex in addition to allow_origins, so both rules are honoured.
    allow_origin_regex=r"http://(192\.168|10\.|172\.(1[6-9]|2\d|3[01]))[\d.]+(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers.
app.include_router(tasks.router, prefix="/api/tasks", tags=["tasks"])
app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
app.include_router(ideas.router, prefix="/api/ideas", tags=["ideas"])
app.include_router(inbox.router, prefix="/api/inbox", tags=["inbox"])
app.include_router(portfolio.router, prefix="/api/portfolio", tags=["portfolio"])
app.include_router(money.router, prefix="/api/money", tags=["money"])
app.include_router(watchlist.router, prefix="/api/watchlist", tags=["watchlist"])
app.include_router(brand.router, prefix="/api/brand", tags=["brand"])
app.include_router(career.router, prefix="/api/career", tags=["career"])
app.include_router(integrations.router, prefix="/api/integrations", tags=["integrations"])
app.include_router(runs.router, prefix="/api/runs", tags=["runs"])
app.include_router(search.router, prefix="/api/search", tags=["search"])
app.include_router(skills.router, prefix="/api/skills", tags=["skills"])
app.include_router(reading.router, prefix="/api/reading", tags=["reading"])
app.include_router(system.router, prefix="/api/system", tags=["system"])


@app.get("/")
def root() -> dict:
    return {"status": "ok", "name": "Personal Command Center API"}


@app.get("/health")
def health() -> dict:
    return {"status": "healthy"}
