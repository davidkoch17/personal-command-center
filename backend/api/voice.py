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
# Phase 13.7: male British voice (Alan). Model + config live in ``backend/voice/piper/``.
_PIPER_MODEL_NAME = "en_GB-alan-medium"
_PIPER_MODEL = _VOICE_DIR / f"{_PIPER_MODEL_NAME}.onnx"

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
    """Transcribe an uploaded audio file via local Whisper.

    Always returns a JSON dict with a ``text`` field (empty on failure) plus an
    ``error`` field when something went wrong, so the frontend can surface the
    cause instead of failing silently. A near-empty upload (silence detection
    fired before any speech) short-circuits with ``error="audio_too_short"``.
    """
    suffix = Path(audio.filename or "recording.webm").suffix or ".webm"
    # NamedTemporaryFile keeps this cross-platform (the spec's hard-coded
    # ``/tmp`` path does not exist on Windows).
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(await audio.read())
            temp_path = Path(tmp.name)
        size = temp_path.stat().st_size
        logger.info("Transcribing %s, size=%d bytes", temp_path, size)
        # A webm header alone is a few hundred bytes; anything this small means
        # silence detection cut before David actually said anything.
        if size < 1000:
            logger.warning("Audio too small (%d bytes), likely no speech", size)
            temp_path.unlink(missing_ok=True)
            return {"text": "", "error": "audio_too_short"}
        try:
            model = _get_whisper()
            result = model.transcribe(str(temp_path), fp16=False, language="en")
        finally:
            temp_path.unlink(missing_ok=True)
        text = result["text"].strip()
        logger.info("Transcribed: %r", text)
        return {"text": text, "language": result.get("language", "en")}
    except Exception as exc:  # noqa: BLE001 - never crash the voice loop silently
        logger.exception("Transcription failed: %s", exc)
        return {"text": "", "error": str(exc)}


class RouteRequest(BaseModel):
    text: str
    current_page: str | None = None
    context: dict | None = None


# Skills Jarvis may trigger by voice (a curated subset of the skills registry).
_VOICE_SKILLS = [
    "market_researcher", "earnings_reviewer", "valuation_reviewer",
    "model_builder", "tax_scenario", "scenario_analyzer",
    "ask_about_project", "draft_first_pass_script", "generate_hook_variants",
    "generate_title_variants", "quiz_technicals", "mock_interview",
]

_UNCLEAR = {"action": "unclear", "spoken_response": "I didn't catch that. Could you repeat?"}

# Injected into both the briefing and (implicitly) the router prompt so spoken
# output names concrete entities instead of generic placeholders.
SPECIFICITY_RULES = """
CRITICAL — be specific:
- Use PROJECT NAMES not generic terms ("Ulli Acebuche deck" not "the deck")
- Use TICKERS not "your portfolio" ("BABA was -2.3% this week" not "your portfolio moved")
- Use EXACT DATES not relative ("by Friday June 6th" not "by end of week")
- Use TASK TEXT not "your todo" ("Verify Miami flights and ESTA" not "your travel task")
- Suggestions must be ACTIONABLE with named items, e.g.:
  - "Open the Ulli Acebuche workspace and finalize Section 3 of the deck"
  - NOT "work on your project"
- When mentioning a project, ALSO include its ID/path: "Ulli (03_Project_Ulli_Acebuche)"
- When mentioning a watchlist name, include the ticker: "Nike (NKE)"
"""


def _build_nav_map() -> dict:
    """Comprehensive navigation target map handed to the router prompt.

    Every URL here is one the React router actually resolves, so Jarvis can
    never navigate to a 404:

    - **pages** mirror the sidebar/router exactly (``journal`` -> the
      decision-journal route, not a non-existent ``/journal``).
    - **projects** are discovered from the vault as full-folder-name workspace
      URLs (the projects API resolves both the folder name and the numeric
      prefix), each with friendly aliases ("ulli", "thesis", "k&e", ...).
    - **ideas** come from the idea-validator's active list — the only ideas
      whose ``/workspace/idea/<name>`` route resolves.
    - **watchlist_tickers** are scraped from the agent's Watchlist.md universe.
    """
    from core import vault
    from core.config import PROJECTS_PATH, WATCHLIST_UNIVERSE_FILE

    nav_map: dict = {
        "pages": {
            "home": "/",
            "tasks": "/tasks",
            "projects": "/projects",
            "ideas": "/ideas",
            "inbox": "/inbox",
            "portfolio": "/portfolio",
            "money": "/money",
            "watchlist": "/watchlist",
            "career": "/career",
            "brand": "/brand",
            "reading": "/reading",
            "background runs": "/background-runs",
            "settings": "/settings",
            "calendar": "/calendar",
            "journal": "/decision-journal",
            "decision journal": "/decision-journal",
        },
        "projects": {},  # name/alias → workspace URL
        "ideas": [],
        "watchlist_tickers": [],
    }

    # Discover projects → full-folder-name workspace URLs, with aliases.
    if PROJECTS_PATH.exists():
        for d in sorted(PROJECTS_PATH.iterdir()):
            if not d.is_dir() or d.name.startswith(("_", ".")) or d.name == "98_Ideen":
                continue
            url = f"/workspace/project/{d.name}"
            nav_map["projects"][d.name.lower()] = url
            # "Short" alias without the numeric prefix.
            short = d.name.split("_", 1)[1] if "_" in d.name else d.name
            nav_map["projects"][short.lower()] = url
            # Spoken nicknames David actually uses.
            if "Thesis" in d.name:
                nav_map["projects"]["thesis"] = url
                nav_map["projects"]["defense"] = url
            if "K&E" in d.name or "KE" in d.name:
                nav_map["projects"]["k&e"] = url
                nav_map["projects"]["ke"] = url
            if "Ulli" in d.name or "Acebuche" in d.name:
                nav_map["projects"]["ulli"] = url
                nav_map["projects"]["acebuche"] = url
            if "Brand" in d.name:
                nav_map["projects"]["brand project"] = url
                nav_map["projects"]["personal brand"] = url
            if "Immos" in d.name:
                nav_map["projects"]["immos"] = url
                nav_map["projects"]["real estate"] = url

    # Active ideas — build straight from the idea-validator so every URL resolves.
    try:
        from modules.agents.skills.idea_validator import runner as iv

        for idea in iv.list_ideas():
            nav_map["ideas"].append({
                "name": idea["name"].replace("_", " "),
                "url": f"/workspace/idea/{idea['name']}",
            })
    except Exception:  # noqa: BLE001 - ideas are best-effort context
        logger.debug("nav_map: ideas unavailable", exc_info=True)

    # Watchlist tickers (e.g. "(NKE)", "(^GSPC)", "(BTC-USD)", "(EURUSD=X)").
    watchlist_md = vault.read_md(WATCHLIST_UNIVERSE_FILE)
    nav_map["watchlist_tickers"] = sorted(
        set(re.findall(r"\(([A-Z0-9.\-^]+(?:=[A-Z]+)?)\)", watchlist_md))
    )
    return nav_map


@router.post("/route")
def route(req: RouteRequest) -> dict:
    """Interpret a spoken command across 9 categories and decide the action.

    Sync handler on purpose: ``run_claude`` blocks ~60s, so FastAPI runs this in
    a worker thread rather than stalling the event loop. Returns a JSON-safe
    dict the Jarvis hook executes (navigate / data_query / run_skill /
    capture_inbox / add_task / toggle_task / add_hypothesis / add_transaction /
    ambiguous / unclear). Malformed model output degrades to an ``unclear``
    fallback, and any failure is logged verbosely so the disconnect is debuggable.
    """
    logger.info("Route request: text=%r page=%r", req.text, req.current_page)
    if not req.text.strip():
        return dict(_UNCLEAR)

    # Contextual data Claude needs to classify and to answer data queries.
    from core import vault
    from core.config import SYSTEM_PATH

    tasks_md = vault.read_md(SYSTEM_PATH / "Task_Command_Center.md")
    projects_md = vault.read_md(SYSTEM_PATH / "Project_Index.md")
    nav_map = _build_nav_map()

    prompt = f"""You are Jarvis, David's command center voice assistant. Interpret his spoken command and return JSON.

David said: "{req.text}"
Current page: {req.current_page or "/"}
Context: {req.context or {}}

AVAILABLE NAVIGATION TARGETS (use these EXACT URLs — never invent a path):

Pages:
{json.dumps(nav_map['pages'], indent=2)}

Projects (workspace URLs — try multiple aliases when matching):
{json.dumps(nav_map['projects'], indent=2)}

Ideas:
{json.dumps(nav_map['ideas'], indent=2)}

Watchlist tickers (open a ticker dossier via /workspace/watchlist/<TICKER>):
{nav_map['watchlist_tickers']}

When David says ambiguous things, ALWAYS prefer the specific target:
- "open Ulli" -> the Ulli project workspace URL above, NOT generic /projects
- "show me Nike" -> /workspace/watchlist/NKE, NOT /watchlist
- "open the deck" -> ambiguous, ASK which deck (Ulli's or the thesis defense?)

You handle 9 command categories. Classify and respond:

1. NAVIGATION — opens a page/workspace in a new tab. Use ONLY a URL listed above.

2. DATA_QUERY — asks for a specific number / fact David wants spoken aloud
   Examples: "what's my net worth", "how many tasks today", "when is the defense"
   You should provide the answer in spoken_response based on context below.

3. RUN_SKILL — triggers a background skill
   Available skills: {_VOICE_SKILLS}

4. CAPTURE_INBOX — saves a thought/note to inbox
   Examples: "note: ...", "remember to ...", "save this idea ..."

5. ADD_TASK — adds a new task to Task_Command_Center.md
   Examples: "add task: ...", "remind me to ...", "I need to ..."

6. TOGGLE_TASK — marks a task done
   Examples: "mark X done", "I finished Y"

7. ADD_HYPOTHESIS — adds an investment hypothesis to Hypothesis_Tracker for a specific ticker
   Examples: "add hypothesis: BABA is undervalued", "hypothesis on Nike: ..."

8. ADD_TRANSACTION — logs a portfolio buy / sell / dividend to the transaction log
   Examples: "I bought 10 shares of Microsoft at 420", "sold 5 Apple at 190", "log a dividend of 12 dollars from Alphabet"
   Map the company/coin to its ticker (Microsoft->MSFT, Apple->AAPL, Alphabet->GOOGL, Alibaba->BABA, BYD->BYDDY, Solana->SOL, Bitcoin->BTC, Ethereum->ETH).

9. CONFIRMATION_NEEDED — when the command is ambiguous, ask back for clarification before acting.

CONTEXT FOR DATA QUERIES (use this to answer):
Task file: {tasks_md[:2000]}
Projects: {projects_md[:1500]}

OUTPUT — JSON only, no other text:
{{
  "action": "navigate" | "data_query" | "run_skill" | "capture_inbox" | "add_task" | "toggle_task" | "add_hypothesis" | "add_transaction" | "ambiguous" | "unclear",
  "navigate_to": "/path",  (if navigate)
  "skill_name": "...", (if run_skill)
  "skill_args": {{...}},  (if run_skill)
  "capture_text": "...",  (if capture_inbox)
  "task_text": "...",  (if add_task — the task wording)
  "task_section": "This week" | "Bigger items" | etc.,  (if add_task)
  "toggle_match": "search string for the task to toggle",  (if toggle_task)
  "hypothesis_ticker": "NKE",  (if add_hypothesis)
  "hypothesis_text": "...",  (if add_hypothesis)
  "transaction": {{"ticker": "MSFT", "action": "buy", "quantity": 10, "price": 420, "currency": "USD"}},  (if add_transaction)
  "clarification_question": "Which deck?",  (if ambiguous — Jarvis will speak this and listen again)
  "answer": "...",  (if data_query — the answer text)
  "spoken_response": "Brief acknowledgment David hears, butler-style, 5-15 words"
}}

Examples:
- "show me my portfolio" -> action: navigate, navigate_to: "/portfolio", spoken_response: "Opening your portfolio."
- "open Ulli" -> action: navigate, navigate_to: "/workspace/project/03_Project_Ulli_Acebuche", spoken_response: "Opening the Ulli Acebuche workspace."
- "show me Nike" -> action: navigate, navigate_to: "/workspace/watchlist/NKE", spoken_response: "Pulling up Nike."
- "what's my net worth" -> action: data_query, answer: "Your current net worth is EUR 4,807 as of May 26th.", spoken_response: "Your net worth is 4,807 euros."
- "note: had an idea about coffee subscriptions" -> action: capture_inbox, capture_text: "Had an idea about coffee subscriptions", spoken_response: "Captured to your inbox."
- "open the deck" -> action: ambiguous, clarification_question: "Which deck — Ulli's or the defense slides?", spoken_response: "Which deck — Ulli's or the defense slides?"
- "run market research" -> action: run_skill, skill_name: "market_researcher", spoken_response: "Running market research now."
- "mark FFM apartment done" -> action: toggle_task, toggle_match: "FFM apartment decision", spoken_response: "Marked FFM apartment done."
- "add hypothesis: Nike margins are recovering" -> action: add_hypothesis, hypothesis_ticker: "NKE", hypothesis_text: "Margins are recovering", spoken_response: "Added Nike hypothesis."
- "I bought 10 shares of Microsoft at 420" -> action: add_transaction, transaction: {{"ticker": "MSFT", "action": "buy", "quantity": 10, "price": 420, "currency": "USD"}}, spoken_response: "Logged: bought 10 Microsoft at 420."
- "what??" / mumbling -> action: unclear, spoken_response: "I didn't catch that. Could you repeat?"

Tone in spoken_response: crisp British butler. Short. Direct. No filler.
"""
    try:
        result = run_claude(prompt, timeout=60)
    except Exception as exc:  # noqa: BLE001 - surface any CLI failure to the caller
        logger.exception("Route: run_claude failed: %s", exc)
        return {"action": "unclear", "spoken_response": f"Something went wrong: {str(exc)[:100]}"}

    # Verbose trace of the raw model output so a disconnect is debuggable.
    logger.info("Route: Claude raw response: %s", result[:500])

    # Parse JSON from the response (Claude may wrap it in a code block / prose).
    match = re.search(r"\{.*\}", result, re.DOTALL)
    if not match:
        logger.warning("Route: no JSON found in model output, falling back to unclear")
        return dict(_UNCLEAR)
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        logger.warning("Route: malformed JSON in model output: %r", match.group(0)[:300])
        return dict(_UNCLEAR)
    logger.info("Route: parsed action=%s -> %s", parsed.get("action"), parsed)
    return parsed


class SpeakRequest(BaseModel):
    text: str
    # 0.85 ≈ 17% faster than Piper's default 1.0; configurable so it can be
    # tuned live from the client without a redeploy.
    length_scale: float = 0.85


@router.post("/speak")
def speak(req: SpeakRequest) -> StreamingResponse:
    """Synthesize text to speech via Piper. Returns a WAV audio stream.

    Piper's ``--output_raw`` emits headerless PCM, which a browser ``Audio``
    element cannot decode, so we have Piper write a proper ``.wav`` to a temp
    file and stream that back instead. ``length_scale`` controls speed (lower =
    faster); the default 0.85 makes Jarvis noticeably snappier.
    """
    if not _PIPER_EXE.exists():
        raise HTTPException(status_code=500, detail="Piper not installed (see README).")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        out_path = Path(tmp.name)
    try:
        proc = subprocess.run(
            [
                str(_PIPER_EXE),
                "--model", str(_PIPER_MODEL),
                "--length-scale", str(req.length_scale),
                "--output_file", str(out_path),
            ],
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

    # Open tasks for the near term — full task text, so the briefing can quote it.
    try:
        tasks_md = vault.read_md(TASKS_FILE)
        bullets = (
            markdown.parse_section_bullets(tasks_md, "This weekend")
            or markdown.parse_section_bullets(tasks_md, "Today")
            or markdown.parse_section_bullets(tasks_md, "This week")
            or []
        )
        unchecked = [b["text"] for b in bullets if not b["checked"]]
        if unchecked:
            parts.append("Open tasks (quote the exact text): " + "; ".join(unchecked[:6]))

        # Immovable real-world deadlines — exact dates, never "end of week".
        hard = [h for h in markdown.parse_hard_dates(tasks_md) if h.get("date")]
        if hard:
            dated = "; ".join(
                f"{h['date'].strftime('%a %b %d')}: {h['label']}" for h in hard[:5]
            )
            parts.append("Hard dates (use the exact date): " + dated)
    except Exception:  # noqa: BLE001 - briefing context is best-effort
        logger.debug("briefing: tasks unavailable", exc_info=True)

    # Portfolio snapshot — name the held tickers, not just a count.
    try:
        from modules.finance.portfolio import combined_holdings, summary_metrics

        m = summary_metrics()
        parts.append(
            f"Portfolio value: EUR {m['total_value']:.0f}, {m['position_count']} "
            f"positions, latest snapshot {m.get('latest_snapshot')}."
        )
        try:
            df = combined_holdings()
            names = [str(n) for n in df.get("Name", []) if str(n).strip()][:8]
            if names:
                parts.append("Held positions: " + ", ".join(names))
        except Exception:  # noqa: BLE001
            logger.debug("briefing: holdings unavailable", exc_info=True)
    except Exception:  # noqa: BLE001
        logger.debug("briefing: portfolio unavailable", exc_info=True)

    # Active project statuses + next steps — include the literal folder names so
    # the briefing can say "Ulli (03_Project_Ulli_Acebuche)" not "your project".
    try:
        proj_md = vault.read_md(PROJECT_INDEX_FILE)
        projects = markdown.parse_projects(proj_md)
        active = [p for p in projects if "done" not in (p.get("status_text") or "").lower()]
        if active:
            named = "; ".join(
                f"{p['folder']} — next: {p.get('next_step') or '(no next step)'}"
                for p in active[:4]
            )
            parts.append(
                f"Active projects ({len(active)}) — use these literal folder names: {named}"
            )
    except Exception:  # noqa: BLE001
        logger.debug("briefing: projects unavailable", exc_info=True)

    # Watchlist universe tickers — so the briefing names tickers, not "the market".
    try:
        from core.config import WATCHLIST_UNIVERSE_FILE

        watchlist_md = vault.read_md(WATCHLIST_UNIVERSE_FILE)
        tickers = sorted(set(re.findall(r"\(([A-Z0-9.\-^]+(?:=[A-Z]+)?)\)", watchlist_md)))
        if tickers:
            parts.append("Watchlist tickers (name tickers, not 'the market'): " + ", ".join(tickers[:20]))
    except Exception:  # noqa: BLE001
        logger.debug("briefing: watchlist unavailable", exc_info=True)

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
{SPECIFICITY_RULES}
Generate output as JSON only, no other text:
{{
  "text": "The full briefing text - 4-6 sentences. Warm but efficient. Names specific projects (with folder IDs), tickers, exact dates, and the literal text of tasks — never generic placeholders.",
  "suggestions": ["Action 1", "Action 2", "Action 3"],
  "spoken": "Shorter spoken version of the briefing - same info but optimized for speaking aloud, ~30-45 seconds when read at normal pace. End with: 'What would you like to start with?'"
}}

The "suggestions" array must hold exactly 3 specific, actionable things David could tackle today, each naming a concrete project / ticker / task drawn from the context (e.g. "Finalize Section 3 of the Ulli Acebuche deck"), never "work on your project".
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
