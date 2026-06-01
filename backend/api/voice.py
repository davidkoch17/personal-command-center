"""Voice (Jarvis) endpoints — local Whisper STT, Claude intent routing, Piper TTS.

The whole pipeline runs locally and free:
- **Transcribe** — OpenAI Whisper (``base`` model) runs on-device. No API key.
- **Route** — Claude (via the local ``claude -p`` CLI on David's Max plan)
  classifies the spoken command into a structured action.
- **Speak** — Piper synthesises a short spoken acknowledgement to WAV.

Heavy/optional dependencies (``whisper``, the Piper binary, FFmpeg) are imported
*lazily inside the handlers* so the backend still boots if voice isn't set up
yet — only the voice routes 500 in that case, the rest of the API is unaffected.
"""
from __future__ import annotations

import io
import json
import re
import subprocess
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from core.config import get_logger
from modules.agents.claude_cli import run_claude

logger = get_logger(__name__)

router = APIRouter()

_VOICE_DIR = Path(__file__).resolve().parent.parent / "voice" / "piper"


def _find_piper_exe() -> Path:
    """Locate piper.exe. The Windows release extracts into a nested ``piper/``
    folder (exe + DLLs alongside); also support a flattened layout."""
    for cand in (_VOICE_DIR / "piper" / "piper.exe", _VOICE_DIR / "piper.exe"):
        if cand.exists():
            return cand
    return _VOICE_DIR / "piper.exe"  # default path for the "not installed" message


_PIPER_EXE = _find_piper_exe()
_PIPER_MODEL = _VOICE_DIR / "en_US-lessac-medium.onnx"

# Lazy-load Whisper — the model download (~150 MB) happens on first use.
_whisper_model = None


def _get_whisper():
    """Return a cached Whisper model, importing + loading lazily on first call."""
    global _whisper_model
    if _whisper_model is None:
        try:
            import whisper  # heavy, optional dependency
        except ImportError as exc:  # pragma: no cover - depends on local install
            raise HTTPException(
                status_code=500,
                detail="Whisper not installed. Run: pip install -r backend/requirements.txt",
            ) from exc
        logger.info("Loading Whisper 'base' model (first call may download ~150 MB)…")
        _whisper_model = whisper.load_model("base")  # base = balanced speed/quality
    return _whisper_model


@router.get("/status")
def status() -> dict:
    """Report which voice components are installed (used by Settings/diagnostics)."""
    try:
        import whisper  # noqa: F401

        whisper_ok = True
    except ImportError:
        whisper_ok = False
    return {
        "whisper_installed": whisper_ok,
        "whisper_loaded": _whisper_model is not None,
        "piper_installed": _PIPER_EXE.exists() and _PIPER_MODEL.exists(),
    }


@router.post("/transcribe")
async def transcribe(audio: UploadFile = File(...)) -> dict:
    """Transcribe an uploaded audio file via local Whisper."""
    suffix = Path(audio.filename or "recording.webm").suffix or ".webm"
    # NamedTemporaryFile keeps this cross-platform (the spec's hard-coded
    # ``/tmp`` path does not exist on Windows).
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await audio.read())
        temp_path = Path(tmp.name)
    try:
        model = _get_whisper()
        result = model.transcribe(str(temp_path), fp16=False)
    finally:
        temp_path.unlink(missing_ok=True)
    return {"text": result["text"].strip(), "language": result.get("language", "en")}


class RouteRequest(BaseModel):
    text: str
    current_page: str | None = None
    context: dict | None = None


@router.post("/route")
def route(req: RouteRequest) -> dict:
    """Interpret a voice command and decide what action to take."""
    if not req.text.strip():
        return {"action": "unclear", "spoken_response": "I didn't catch that, could you repeat?"}

    prompt = f"""You are a voice command router for David's personal command center dashboard.

User said: "{req.text}"
Current page: {req.current_page or "unknown"}

Classify the intent. Respond with JSON only (no other text):
{{
  "action": "navigate" | "run_skill" | "capture_inbox" | "answer" | "unclear",
  "navigate_to": "/portfolio" | "/tasks" | etc.  (only if action = navigate),
  "skill_name": "market_researcher" | "tax_scenario" | etc.  (only if action = run_skill),
  "skill_args": {{ "key": "value" }}  (only if action = run_skill),
  "capture_text": "..."  (only if action = capture_inbox),
  "answer_text": "..."  (only if action = answer, brief 1-2 sentence spoken response),
  "spoken_response": "Acknowledgment David hears — keep short, like a butler"
}}

Valid navigate targets: /, /tasks, /projects, /ideas, /inbox, /portfolio, /money,
/watchlist, /brand, /career, /reading, /background-runs, /settings, /calendar.

Examples:
- "Show me my portfolio" -> action: navigate, navigate_to: "/portfolio", spoken_response: "Opening your portfolio."
- "Run market research" -> action: run_skill, skill_name: "market_researcher", spoken_response: "Running market research now."
- "Note: I had an idea about a coffee subscription service" -> action: capture_inbox, capture_text: "...", spoken_response: "Captured to your inbox."
- "What's my net worth?" -> action: answer, answer_text: "(query data and respond)", spoken_response: "Your current net worth is X euros."
- Anything ambiguous -> action: unclear, spoken_response: "I didn't catch that, could you repeat?"
"""
    try:
        result = run_claude(prompt, timeout=60)
    except Exception as exc:  # noqa: BLE001 - surface any CLI failure to the caller
        logger.warning("Voice route failed: %s", exc)
        return {"action": "unclear", "spoken_response": "Something went wrong, try again."}

    # Parse JSON from the response (Claude may wrap it in a code block / prose).
    match = re.search(r"\{.*\}", result, re.DOTALL)
    if not match:
        return {"action": "unclear", "spoken_response": "I didn't understand."}
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return {"action": "unclear", "spoken_response": "I didn't understand."}


class SpeakRequest(BaseModel):
    text: str


@router.post("/speak")
def speak(req: SpeakRequest) -> StreamingResponse:
    """Synthesize text to speech via Piper. Returns a WAV audio stream.

    Piper's ``--output_raw`` emits headerless PCM, which a browser ``Audio``
    element cannot decode, so we have Piper write a proper ``.wav`` to a temp
    file and stream that back instead.
    """
    if not _PIPER_EXE.exists():
        raise HTTPException(status_code=500, detail="Piper not installed (see README).")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        out_path = Path(tmp.name)
    try:
        proc = subprocess.run(
            [str(_PIPER_EXE), "--model", str(_PIPER_MODEL), "--output_file", str(out_path)],
            input=req.text.encode("utf-8"),
            capture_output=True,
        )
        if proc.returncode != 0:
            logger.warning("Piper failed: %s", proc.stderr.decode("utf-8", "replace"))
            raise HTTPException(status_code=500, detail="Speech synthesis failed.")
        audio_bytes = out_path.read_bytes()
    finally:
        out_path.unlink(missing_ok=True)
    return StreamingResponse(io.BytesIO(audio_bytes), media_type="audio/wav")


def _assemble_briefing_context() -> str:
    """Gather a compact snapshot of David's world for the opening briefing.

    Every source is best-effort: a missing file or unconfigured integration is
    skipped rather than failing the whole briefing.
    """
    from datetime import date

    from core import markdown, vault
    from core.config import PROJECT_INDEX_FILE, TASKS_FILE

    parts: list[str] = []

    today = date.today()
    parts.append(f"Today is {today.strftime('%A, %B %d, %Y')}.")

    # Open tasks for the near term.
    try:
        tasks_md = vault.read_md(TASKS_FILE)
        bullets = (
            markdown.parse_section_bullets(tasks_md, "This weekend")
            or markdown.parse_section_bullets(tasks_md, "Today")
            or []
        )
        unchecked = [b["text"] for b in bullets if not b["checked"]]
        if unchecked:
            parts.append("Open tasks for today: " + "; ".join(unchecked[:6]))
    except Exception:  # noqa: BLE001 - briefing context is best-effort
        logger.debug("briefing: tasks unavailable", exc_info=True)

    # Portfolio snapshot.
    try:
        from modules.finance.portfolio import summary_metrics

        m = summary_metrics()
        parts.append(
            f"Portfolio value: EUR {m['total_value']:.0f}, {m['position_count']} "
            f"positions, latest snapshot {m.get('latest_snapshot')}."
        )
    except Exception:  # noqa: BLE001
        logger.debug("briefing: portfolio unavailable", exc_info=True)

    # Active project statuses + next steps.
    try:
        proj_md = vault.read_md(PROJECT_INDEX_FILE)
        projects = markdown.parse_projects(proj_md)
        active = [p for p in projects if "done" not in (p.get("status_text") or "").lower()]
        if active:
            steps = "; ".join(p["next_step"] for p in active[:3] if p.get("next_step"))
            parts.append(f"Active projects: {len(active)}. Next steps: {steps}")
    except Exception:  # noqa: BLE001
        logger.debug("briefing: projects unavailable", exc_info=True)

    # Most recent market brief.
    try:
        from modules.agents.market_researcher import BRIEFS_DIR

        latest = sorted(BRIEFS_DIR.glob("*.md"), reverse=True)
        if latest:
            parts.append(f"Latest market brief: {latest[0].stem}.")
    except Exception:  # noqa: BLE001
        logger.debug("briefing: market briefs unavailable", exc_info=True)

    return "\n".join(parts)


@router.post("/briefing")
def briefing() -> dict:
    """Generate David's opening briefing: text, 3 suggestions, and a spoken version.

    Sync (not ``async``) on purpose: ``run_claude`` is a blocking ~60s subprocess,
    so FastAPI runs this in a worker thread instead of stalling the event loop.
    """
    context_text = _assemble_briefing_context()

    prompt = f"""You are David's command center assistant. Generate a brief, warm morning briefing for him based on the context below.

Context:
{context_text}

Generate output as JSON only, no other text:
{{
  "text": "The full briefing text - 4-6 sentences. Warm but efficient. Mentions key facts about today, portfolio, projects.",
  "suggestions": ["Action 1", "Action 2", "Action 3"],
  "spoken": "Shorter spoken version of the briefing - same info but optimized for speaking aloud, ~30-45 seconds when read at normal pace. End with: 'What would you like to start with?'"
}}

The "suggestions" array must hold exactly 3 specific things David could tackle today, derived from the context.
Tone: like a competent chief of staff giving a morning update. Direct, no fluff, no emojis.
"""
    fallback = {
        "text": "Good morning, David.",
        "suggestions": [],
        "spoken": "Good morning, David. What would you like to work on?",
    }
    try:
        result = run_claude(prompt, timeout=60)
    except Exception:  # noqa: BLE001 - never let the briefing hard-fail the UI
        logger.warning("briefing: run_claude failed", exc_info=True)
        return fallback

    match = re.search(r"\{.*\}", result, re.DOTALL)
    if not match:
        return fallback
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return fallback
