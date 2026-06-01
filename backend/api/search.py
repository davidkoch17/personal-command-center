"""Search API — full-text vault search."""
from __future__ import annotations

from fastapi import APIRouter, Query

from backend.models.schemas import SearchResult, SearchResponse
from modules.search import index

router = APIRouter()


@router.get("")
def search(q: str = Query("", description="Search query"),
           limit: int = Query(30, ge=1)) -> SearchResponse:
    """Case-insensitive literal search across vault .md/.txt files."""
    results = []
    for r in index.search(q, limit=limit):
        mtime = r.get("mtime")
        results.append(SearchResult(
            relative_path=r.get("relative", ""),
            snippet=r.get("snippet", ""),
            match_count=r.get("match_count", 0),
            mtime=mtime.isoformat() if hasattr(mtime, "isoformat") else None,
        ))
    return SearchResponse(query=q, results=results)
