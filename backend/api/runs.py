"""Background runs API — list, status, and live WebSocket log streaming."""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect

from modules.agents import background
from modules.agents.background import BG_LOG_DIR

router = APIRouter()


@router.get("")
def list_runs(limit: int = Query(20, ge=1)) -> dict:
    """List the most recent background runs (status + metadata)."""
    return {"runs": background.list_recent_runs(limit)}


@router.get("/{run_id}")
def run_status(run_id: str) -> dict:
    """Status of a single background run by id."""
    status = background.get_status(run_id)
    status.setdefault("run_id", run_id)
    return status


@router.post("/{run_id}/cancel")
def cancel_run(run_id: str) -> dict:
    """Kill a run's detached subprocess and mark it cancelled."""
    return background.cancel(run_id)


@router.post("/{run_id}/restart")
def restart_run(run_id: str) -> dict:
    """Relaunch a run with its original module/callable/args (new run_id)."""
    result = background.restart(run_id)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("detail", "cannot restart"))
    return result


@router.websocket("/{run_id}/stream")
async def stream_run(websocket: WebSocket, run_id: str) -> None:
    """Stream status snapshots + log deltas for a run until it finishes."""
    await websocket.accept()
    log_path = BG_LOG_DIR / f"{run_id}.log"
    status_path = BG_LOG_DIR / f"{run_id}.status.json"

    last_size = 0
    try:
        while True:
            # Send status snapshot.
            if status_path.exists():
                try:
                    status = json.loads(status_path.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    status = {"status": "unknown"}
                await websocket.send_json({"type": "status", "data": status})
                if status.get("status") in {"completed", "failed"}:
                    # Flush any remaining log before closing.
                    if log_path.exists() and log_path.stat().st_size > last_size:
                        with open(log_path, "rb") as f:
                            f.seek(last_size)
                            tail = f.read().decode("utf-8", errors="replace")
                        await websocket.send_json({"type": "log", "data": tail})
                    break

            # Send log delta.
            if log_path.exists():
                current_size = log_path.stat().st_size
                if current_size > last_size:
                    with open(log_path, "rb") as f:
                        f.seek(last_size)
                        new_content = f.read().decode("utf-8", errors="replace")
                    await websocket.send_json({"type": "log", "data": new_content})
                    last_size = current_size

            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass
