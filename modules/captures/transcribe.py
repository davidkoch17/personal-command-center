"""Local Whisper transcription for voice captures (reuses the Jarvis model).

Same engine as the Jarvis voice bar (OpenAI Whisper ``base``, on-device, free),
loaded once and cached process-wide. The only difference from the live voice
endpoint: language is **auto-detected** here (``language=None``) instead of
forced to English, because David's voice notes are German or English (spec § b
"deu+eng"). Whisper handles both and reports the detected language.

Whisper needs FFmpeg on PATH to decode ``.m4a``/``.wav``/etc.
"""
from __future__ import annotations

from pathlib import Path

from core.config import get_logger

logger = get_logger(__name__)

# Cached Whisper model (process-wide). The first call downloads ~150 MB.
_whisper_model = None


class TranscriptionUnavailable(RuntimeError):
    """Raised when Whisper (or FFmpeg) is not installed/usable."""


def _get_whisper():
    """Load + cache the Whisper ``base`` model (the same one Jarvis uses)."""
    global _whisper_model
    if _whisper_model is None:
        try:
            import whisper  # heavy, optional dependency
        except ImportError as exc:  # pragma: no cover - depends on local install
            raise TranscriptionUnavailable(
                "Whisper not installed. Run: pip install -r backend/requirements.txt"
            ) from exc
        logger.info("Loading Whisper 'base' model (first call may download ~150 MB)…")
        _whisper_model = whisper.load_model("base")
    return _whisper_model


def transcribe_audio(audio_path: Path) -> tuple[str, str | None]:
    """Transcribe a voice file. Returns ``(transcript, detected_language)``.

    Language is auto-detected (German or English). Raises
    :class:`TranscriptionUnavailable` if Whisper/FFmpeg is missing so the
    watcher can log-and-skip and retry the capture on the next poll.
    """
    try:
        model = _get_whisper()
        # fp16=False: CPU-safe. language=None: auto-detect deu/eng.
        result = model.transcribe(str(audio_path), fp16=False, language=None)
    except TranscriptionUnavailable:
        raise
    except Exception as exc:  # noqa: BLE001 - surface decode/runtime failures
        raise TranscriptionUnavailable(str(exc)) from exc
    text = (result.get("text") or "").strip()
    lang = result.get("language")
    logger.info("Transcribed %s -> %d chars (lang=%s)", audio_path.name, len(text), lang)
    return text, lang
