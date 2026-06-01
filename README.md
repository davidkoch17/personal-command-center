# Personal Command Center

Dashboard for David's tasks, projects, finances, agents, ideas. React frontend + FastAPI backend + Python modules wrapping Claude Code skills.

## Run

Double-click `start_dashboard.bat`. It builds the React frontend, then starts
the FastAPI backend, which serves both the API and the app at
http://localhost:8000.

## Architecture

- `backend/` — FastAPI exposing all logic as REST + WebSocket (and serving the built React app)
- `frontend/` — React (Vite + TS + Tailwind), Cockpit design system
- `modules/` — Python skills, agents, integrations (unchanged from Streamlit days)
- `core/` — shared utilities, vault helpers
- `_legacy/` — archived Streamlit dashboard

## Stack

Python 3.12 + FastAPI · React 18 + TypeScript + Vite · Tailwind CSS · TanStack Query · Claude Code (via subprocess) · Whisper local STT · Piper local TTS · yfinance · Alpha Vantage · Microsoft Graph (via iCal feed) · Whoop · Kraken · GitHub · YouTube

## Development

Three servers can run independently:
- `start_backend.bat` — backend only (8000)
- `start_frontend.bat` — Vite dev server (5173, hot reload, talks to backend on 8000)
- `start_dashboard.bat` — production build + serve (8000 only)

Requires **Node.js 18+** (https://nodejs.org) for the frontend and **Python
3.12+** for the backend. During frontend development the Vite server proxies to
the backend at `http://localhost:8000` (override with `VITE_API_BASE`).

## Setup
See `99_System/Credentials_Setup_Guide.md` for one-time API credentials.
See `99_System/Design_System.md` for the Cockpit visual language.

## One-click launch (Windows desktop shortcut)

1. Right-click on your Desktop → New → Shortcut.
2. Location: `C:\Users\david\Desktop\claude code\personal_command_center\start_dashboard.bat`
3. Name: `Command Center`.
4. Optional: right-click the shortcut → Properties → Change Icon → pick anything (e.g. a chart icon).

Double-click the icon to launch dashboard. Browser opens automatically.

## Access from iPad / phone

1. Make sure your laptop is on the same Wi-Fi as the iPad.
2. On the laptop, find your local IP: open PowerShell, run `ipconfig` — look for "IPv4 Address" under your active adapter (usually `192.168.x.x`).
3. On the iPad, open Safari → `http://<your-laptop-ip>:8000`.
4. Bookmark to home screen for one-tap access.

Note: only works while laptop is on + the backend is running.

**Security:** the dashboard is wide-open on your local network — anyone on your Wi-Fi can reach it. Fine at home. If on public Wi-Fi (coffee shop, hotel), either don't run it OR set address back to `localhost`.

## Voice / Jarvis (Phase 13)

A hold-to-talk voice layer lives in the bottom-center bar of the React
frontend. Everything runs locally and free: Whisper transcribes, Claude (the
local `claude -p` CLI) routes the command to an action (navigate, run a skill,
capture to inbox, or answer), and Piper speaks a short acknowledgement.

**One-time setup:**

1. **FFmpeg** (Whisper needs it): `winget install ffmpeg` (or use chocolatey).
   Open a new terminal afterwards so it's on PATH.
2. **Piper** (text-to-speech):
   - Download the latest Windows release from
     https://github.com/rhasspy/piper/releases and extract so that
     `backend/voice/piper/piper.exe` exists.
   - Download the `en_US-lessac-medium` voice (both `.onnx` and `.onnx.json`)
     from https://huggingface.co/rhasspy/piper-voices and place them in
     `backend/voice/piper/`.
   - See `backend/voice/piper/README.md` for exact paths. These files are
     gitignored (large, per-machine).
3. **Backend Python deps** (installs Whisper + Porcupine):
   `pip install -r backend/requirements.txt`
4. **First run** downloads the Whisper `base` model (~150 MB) — the first
   transcription will be slow while it downloads, then it's cached.
5. **(Optional, future) wake word** ("Hey Claude"): get a free Picovoice access
   key at https://console.picovoice.ai/ and add it to `.env` as `PICOVOICE_KEY`.
   Phase 13 ships push-to-talk only; the Settings toggle is a placeholder.
6. Grant the browser microphone permission when first prompted.

Settings → "voice (jarvis)" shows whether Whisper and Piper are installed
(`GET /api/voice/status`).

**Usage:** hold the bar, speak ("show me my portfolio", "run market research",
"note: idea about a coffee subscription", "what's my net worth?"), release.

## Backup to private GitHub

The code repo lives on Desktop; OneDrive does NOT cover it. Push to a private GitHub repo for offsite backup.

1. Create a private repo at https://github.com/new — name: `personal-command-center`, visibility: Private.
2. Locally, in PowerShell at the project root:

```
git remote add origin https://github.com/<your-username>/personal-command-center.git
git branch -M main
git push -u origin main
```

3. Subsequent pushes: just `git push`. Recommend pushing after each commit.

`.env` is gitignored — credentials never reach GitHub.

## Keyboard shortcuts

- **Ctrl+1** — Home
- **Ctrl+2** — Tasks
- **Ctrl+3** — Projects
- **Ctrl+I** — Inbox
- **Ctrl+/** — Search

## Structure
- `backend/` — FastAPI REST + WebSocket layer (serves the built React app)
- `frontend/` — React (Vite + TS + Tailwind) Cockpit UI
- `core/` — config, vault reader
- `modules/` — domain logic (tasks, projects, investing, habits, agents, integrations)
- `skills/` — runnable scripts
- `data/` — local cache (gitignored)
- `_legacy/` — archived Streamlit dashboard (Phases 1-10)

## Build phases
- Phase 1: empty shell with placeholder data
- Phase 2: live vault reading + writes
- Phase 3: portfolio + watchlist static
- Phase 4: live financial data
- Phase 5: agents + skills
- Phase 6: external integrations
- Phase 7: operational polish (theme, search, diagnostics, caching, shortcuts, mobile access)
- Phases 11-13: React + FastAPI rebuild (Cockpit UI, background runs, Jarvis voice)
- Phase 14: switch over — React Cockpit becomes primary, Streamlit archived to `_legacy/`

## Agents & Skills (Phase 5)

Inference runs on David's Claude Max subscription via the `claude -p` CLI — no
Anthropic API key, zero per-call cost. Calls are slow (~10-60s; the weekly brief
can take a few minutes) but free.

- **Market Researcher** (Agents page) — weekly equity research brief across the
  watchlist universe (`4_Areas/Investing/Watchlist.md`). Writes briefs to
  `4_Areas/Investing/Market_Briefs/YYYY-MM-DD.md` and maintains
  `Hypothesis_Tracker.md`.
- **Skills** (Skills page) — Earnings Reviewer, Valuation Reviewer, Model Builder.
- **Ask Claude about this project** (Projects page) — answers with the project's
  key files loaded as context.

## Weekly Market Researcher run

To enable the Sunday 19:00 auto-run:

1. Open Task Scheduler (Win+R, type `taskschd.msc`).
2. Create Task → name "Market Researcher".
3. Trigger: weekly, Sunday, 19:00.
4. Action: Start a program → point it at `run_market_researcher.bat` in the
   project directory (or run `python` with arguments
   `-m modules.agents.market_researcher`, "Start in" set to the project dir).
5. Tick "Run whether user is logged on or not" for headless runs.

Until this is set up, run manually from the Agents page (**Run now**) or by
double-clicking `run_market_researcher.bat`.

## Integrations (Phase 6)

Eight external integrations. **Every one degrades gracefully** — if its
credentials are missing it shows "Not configured — add KEY to .env" instead of
crashing. Copy `.env.example` to `.env` and fill in the keys you want, then
restart the backend. Keys can be added progressively.

| Integration | Keys in `.env` | Where it shows |
|---|---|---|
| Calendar (iCal) | `OUTLOOK_ICAL_URL` | Home + Calendar page |
| Whoop | `WHOOP_CLIENT_ID/SECRET/REFRESH_TOKEN` | Home + Health page |
| TradingView | _(none)_ | Portfolio + Watchlist charts |
| GitHub | `GITHUB_PAT`, `GITHUB_USERNAME` | Settings + Home |
| Kraken | `KRAKEN_API_KEY/SECRET` | Portfolio → Money tab |
| Alpha Vantage | `ALPHA_VANTAGE_KEY` | Market Researcher news |
| YouTube | `YOUTUBE_API_KEY` | Brand → Inspirations |
| Travel | _(none — vault file)_ | Home + Settings |

### Calendar (iCal) setup
1. Open Outlook web (`outlook.live.com` personal, `outlook.office.com` work).
2. Settings → View all Outlook settings → Calendar → Shared calendars.
3. Under "Publish a calendar": select calendar, permission "Can view all details", click Publish.
4. Copy the **ICS** link (not the HTML one) into `.env` as `OUTLOOK_ICAL_URL`.

### Whoop setup
1. developer.whoop.com → sign in → Register an app ("Personal Command Center").
2. Scopes: `read:recovery read:sleep read:profile read:cycles read:workout`. Redirect URI: `http://localhost:8501`.
3. Copy Client ID + Secret into `.env`.
4. Run once: `python -m modules.integrations.whoop_auth` — authorize in the browser, paste the printed refresh token into `.env` as `WHOOP_REFRESH_TOKEN`.

### Kraken setup
account.kraken.com → Security → API → New key with **read-only** permissions
(Query Funds, Query Open Orders & Trades). Paste key + secret into `.env`.

### Travel
Edit `2_Personal/06_Travel/Trips.md` in the vault. Under `## Upcoming`, add
`### YYYY-MM-DD — Destination` headings with `- detail` bullets.
