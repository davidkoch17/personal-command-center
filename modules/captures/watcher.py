"""Polling watcher for the capture inbox folders.

**Polling, not filesystem events** — OneDrive sync makes ``watchdog`` events
unreliable (files appear via sync, not local writes), so this scans both inbox
folders every ``CAPTURE_WATCHER_INTERVAL_SECONDS`` (default 60s) for any sidecar
``.json`` whose ``id`` is not yet in the DB and ingests it.

Run as a long-lived job::

    python -m modules.captures.watcher            # poll forever (60s)
    python -m modules.captures.watcher --once     # single scan, then exit
    python -m modules.captures.watcher --interval 30
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import time
from pathlib import Path

from core.config import (
    CAPTURE_WATCHER_INTERVAL_SECONDS,
    NEWS_CAPTURES_PATH,
    VOICE_NOTES_PATH,
    get_logger,
)
from modules.captures import db
from modules.captures.pipeline import CaptureSkip, process_capture, read_sidecar

logger = get_logger(__name__)

_INBOX_FOLDERS = (NEWS_CAPTURES_PATH, VOICE_NOTES_PATH)


def find_sidecars() -> list[Path]:
    """All sidecar ``.json`` files under both inbox folders (date subfolders)."""
    out: list[Path] = []
    for folder in _INBOX_FOLDERS:
        if folder.exists():
            out.extend(sorted(folder.rglob("*.json")))
    return out


def scan_once() -> list[dict]:
    """Process every not-yet-ingested sidecar. Returns the new summaries.

    Reads the set of known ids once up front to cheaply skip already-ingested
    captures without touching OCR/Whisper/Claude. Per-capture errors are logged
    and skipped so one bad file never stalls the whole inbox.
    """
    db.init_db()
    known = db.existing_ids()
    summaries: list[dict] = []
    for sidecar in find_sidecars():
        try:
            meta = read_sidecar(sidecar)
        except Exception as exc:  # noqa: BLE001 - malformed/partial sync
            logger.warning("skip unreadable sidecar %s: %s", sidecar.name, exc)
            continue
        if meta.get("id") in known:
            continue
        try:
            summary = process_capture(sidecar)
        except CaptureSkip as exc:
            logger.info("defer %s: %s", sidecar.name, exc)
            continue
        except Exception as exc:  # noqa: BLE001 - never let one capture kill the loop
            logger.exception("failed to process %s: %s", sidecar.name, exc)
            continue
        if summary is not None:
            summaries.append(summary)
    if summaries:
        logger.info("scan ingested %d new capture(s)", len(summaries))
    return summaries


def run(interval: int = CAPTURE_WATCHER_INTERVAL_SECONDS) -> None:
    """Poll the inbox folders forever (Ctrl-C to stop)."""
    logger.info(
        "capture watcher started (interval=%ds) watching:\n  %s\n  %s",
        interval, NEWS_CAPTURES_PATH, VOICE_NOTES_PATH,
    )
    while True:
        try:
            scan_once()
        except Exception:  # noqa: BLE001 - keep the loop alive across any failure
            logger.exception("scan_once failed; continuing")
        time.sleep(interval)


async def scheduler_loop(interval: int = CAPTURE_WATCHER_INTERVAL_SECONDS) -> None:
    """Backend-internal capture poller (Phase G), started from the FastAPI lifespan.

    Folds the standalone watcher into the dashboard backend so "dashboard running
    = captures ingested" — no separate scheduled task. ``scan_once`` does OCR /
    Whisper / Claude work, so it runs in a worker thread to keep the event loop
    free. The standalone ``python -m modules.captures.watcher`` entry point still
    works for running the poller on its own.
    """
    logger.info(
        "capture scheduler started (interval=%ds) watching:\n  %s\n  %s",
        interval, NEWS_CAPTURES_PATH, VOICE_NOTES_PATH,
    )
    while True:
        try:
            await asyncio.to_thread(scan_once)
        except Exception:  # noqa: BLE001 - keep the loop alive across any failure
            logger.exception("capture scan_once failed; continuing")
        await asyncio.sleep(interval)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    parser = argparse.ArgumentParser(description="Capture inbox polling watcher")
    parser.add_argument("--once", action="store_true", help="single scan, then exit")
    parser.add_argument(
        "--interval", type=int, default=CAPTURE_WATCHER_INTERVAL_SECONDS,
        help="poll interval in seconds (default 60)",
    )
    args = parser.parse_args()
    if args.once:
        results = scan_once()
        logger.info("done: %d new capture(s)", len(results))
    else:
        run(args.interval)


if __name__ == "__main__":
    main()
