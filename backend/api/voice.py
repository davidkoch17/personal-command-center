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
_PIPER_EXE = _VOICE_DIR / "piper.exe"
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
