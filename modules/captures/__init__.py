"""Phase A capture pipeline.

iOS Shortcut -> OneDrive inbox -> local processing (OCR / Whisper / Claude
enrich) -> SQLite ``captures.db`` (the source of truth). The original media
files are never mutated — they are the backup.

Modules:
- :mod:`modules.captures.db` — schema + connection + CRUD.
- :mod:`modules.captures.ocr` — Tesseract OCR (``deu+eng``).
- :mod:`modules.captures.transcribe` — local Whisper (the Jarvis ``base`` model).
- :mod:`modules.captures.enrich` — Claude enrich + voice auto-classify.
- :mod:`modules.captures.pipeline` — process one capture end-to-end + routing.
- :mod:`modules.captures.watcher` — 60s polling loop over the two inbox folders.
"""
