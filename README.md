# Personal Command Center

A local Streamlit dashboard surfacing David's tasks, projects, finances, and habits — all reading from his Obsidian vault in OneDrive.

## Install
pip install -r requirements.txt

## Run
streamlit run dashboard/Home.py

The dashboard opens at http://localhost:8501.

## Development: three servers

The project runs three independent servers during development. They coexist
peacefully on separate ports — start whichever you need.

| Server | Port | Launcher | Purpose |
|---|---|---|---|
| Streamlit dashboard | 8501 | `start_dashboard.bat` | original UI (still fully functional) |
| FastAPI backend | 8000 | `start_backend.bat` | REST + WebSocket API wrapping the Python modules |
| React frontend | 5173 | `start_frontend.bat` | new Cockpit-themed UI (Phase 12+) |

### React frontend (Vite + TypeScript + Tailwind)

Lives in `frontend/`. Requires **Node.js 18+** (install from https://nodejs.org).

First-time / one-click launch:

```
start_frontend.bat
```

This runs `npm install` (slow on first run) then `npm run dev`, serving the
Cockpit shell at http://localhost:5173.

Manual:

```
cd frontend
npm install      # one-time
npm run dev
```

The frontend talks to the FastAPI backend at `http://localhost:8000` by default.
Override with a `VITE_API_BASE` env var (e.g. in `frontend/.env.local`) if the
backend runs elsewhere. For full functionality, start the backend
(`start_backend.bat`) alongside the frontend.

Like the Streamlit dashboard, the Vite dev server binds to the LAN
(`host: true`), so an iPad/phone on the same Wi-Fi can reach it at
`http://<your-laptop-ip>:5173`.

## One-click launch (Windows desktop shortcut)

1. Right-click on your Desktop → New → Shortcut.
2. Location: `C:\Users\david\Desktop\claude code\personal_command_center\start_dashboard.bat`
3. Name: `Command Center`.
4. Optional: right-click the shortcut → Properties → Change Icon → pick anything (e.g. a chart icon).

Double-click the icon to launch dashboard. Browser opens automatically.

## Access from iPad / phone

1. Make sure your laptop is on the same Wi-Fi as the iPad.
2. On the laptop, find your local IP: open PowerShell, run `ipconfig` — look for "IPv4 Address" under your active adapter (usually `192.168.x.x`).
3. On the iPad, open Safari → `http://<your-laptop-ip>:8501`.
4. Bookmark to home screen for one-tap access.

Note: only works while laptop is on + Streamlit is running.

**Security:** the dashboard is wide-open on your local network — anyone on your Wi-Fi can reach it. Fine at home. If on public Wi-Fi (coffee shop, hotel), either don't run it OR set address back to `localhost`.

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
- `dashboard/` — Streamlit UI (home page + sidebar pages)
- `core/` — config, vault reader
- `modules/` — domain logic (tasks, projects, investing, habits)
- `skills/` — runnable scripts (later phases)
- `data/` — local cache (gitignored)

## Build phases
- Phase 1: empty shell with placeholder data (current)
- Phase 2: live vault reading + writes
- Phase 3: portfolio + watchlist static
- Phase 4: live financial data
- Phase 5: agents + skills
- Phase 6: external integrations
- Phase 7: operational polish (theme, search, diagnostics, caching, shortcuts, mobile access)

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
restart Streamlit. Keys can be added progressively.

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
