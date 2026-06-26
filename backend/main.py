"""FastAPI backend for the Personal Command Center.

Run (development):
    uvicorn backend.main:app --reload --port 8000

Run (LAN, for iPad access during dev):
    python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
    (see ``start_backend.bat``)

As of Phase 14 this is the *single* server: it exposes the API under ``/api``
**and** serves the production React build (``frontend/dist``) for every other
path, so ``http://localhost:8000`` is the whole app. The Streamlit dashboard is
archived in ``_legacy/`` and no longer runs alongside it.

All business logic lives in ``core`` / ``modules``; this layer only adapts it
to HTTP.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.api import (
    tasks, projects, ideas, inbox, portfolio, money,
    watchlist, brand, career, integrations, runs,
    search, skills, reading, system, voice, daily,
    planner, chat, home, captures, research,
)
from backend.api import finance
from modules.briefings import weekly


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Start background schedulers for the lifetime of the server.

    Weekly briefing (Item #16): fires Sunday 18:00; if the laptop was off at
    trigger time, the next backend start catches up (see modules/briefings/weekly).
    """
    briefing_task = asyncio.create_task(weekly.scheduler_loop())
    yield
    briefing_task.cancel()


app = FastAPI(
    title="Personal Command Center API",
    description="Backend for David's command center dashboard",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — only needed for the Vite dev server (5173); in production the app is
# served same-origin from this backend, so no cross-origin request is made.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # Vite dev
        "http://localhost:3000",   # alt dev port
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
app.include_router(finance.router, prefix="/api/finance", tags=["finance"])
app.include_router(money.router, prefix="/api/money", tags=["money"])
app.include_router(watchlist.router, prefix="/api/watchlist", tags=["watchlist"])
app.include_router(captures.router, prefix="/api/captures", tags=["captures"])
app.include_router(research.router, prefix="/api/research", tags=["research"])
app.include_router(brand.router, prefix="/api/brand", tags=["brand"])
app.include_router(career.router, prefix="/api/career", tags=["career"])
app.include_router(integrations.router, prefix="/api/integrations", tags=["integrations"])
app.include_router(runs.router, prefix="/api/runs", tags=["runs"])
app.include_router(search.router, prefix="/api/search", tags=["search"])
app.include_router(skills.router, prefix="/api/skills", tags=["skills"])
app.include_router(reading.router, prefix="/api/reading", tags=["reading"])
app.include_router(system.router, prefix="/api/system", tags=["system"])
app.include_router(voice.router, prefix="/api/voice", tags=["voice"])
app.include_router(daily.router, prefix="/api/daily", tags=["daily"])
app.include_router(planner.router, prefix="/api/planner", tags=["planner"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(home.router, prefix="/api/home", tags=["home"])


@app.get("/health")
def health() -> dict:
    return {"status": "healthy"}


# --- Serve the production React build ---------------------------------------
# Registered last so the API routers and ``/health`` always win; everything
# else falls through to the SPA. The ``/{full_path:path}`` catch-all also
# serves real built files (favicon, etc.) and otherwise returns index.html so
# client-side routing works on a hard refresh / deep link.
DIST_PATH = Path(__file__).parent.parent / "frontend" / "dist"
if DIST_PATH.exists():
    app.mount("/assets", StaticFiles(directory=str(DIST_PATH / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_react(full_path: str):
        """Catch-all: serve a built file if it exists, else index.html (SPA routing)."""
        if full_path:
            candidate = (DIST_PATH / full_path).resolve()
            # Guard against path traversal escaping the dist directory.
            if DIST_PATH.resolve() in candidate.parents and candidate.is_file():
                return FileResponse(candidate)
        return FileResponse(DIST_PATH / "index.html")
