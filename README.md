# Personal Command Center

A local Streamlit dashboard surfacing David's tasks, projects, finances, and habits — all reading from his Obsidian vault in OneDrive.

## Install
pip install -r requirements.txt

## Run
streamlit run dashboard/Home.py

The dashboard opens at http://localhost:8501.

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
