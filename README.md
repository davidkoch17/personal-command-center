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
