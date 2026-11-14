# Personal Command Center — Architecture Breakdown

> **Purpose of this document.** A complete, factual map of the system as of **2026-11-14**, written so another AI (or engineer) can understand every layer and help redesign it. It describes what exists and what is broken — it deliberately does **not** prescribe the redesign. Section 14 lists the open questions the redesign has to answer; the owner (David) decides those.
>
> Sources: direct code reading of the repo, the live route table of the running FastAPI app, and spot checks of the live system (logs, vault folders, Windows Task Scheduler). Facts marked **[verified]** were re-checked on the live machine. Secrets are never included — environment variables are listed by name only.

---

## 0. One-paragraph summary

A **single-user, local-first personal dashboard** for David (finance professional, started at Evercore on 2026-07-01). A **FastAPI** backend (Python 3.12, ~27.5k lines) runs on his Windows laptop on port **8000** and also serves a **React + TypeScript** single-page app (~30k lines) built with Vite. Data lives in three places: (1) his **Obsidian vault in OneDrive** (Markdown, an Excel workbook, `todos.json`), (2) repo-local **`data/`** files (JSONL/JSON/CSV ledgers, a SQLite DB, parquet caches), and (3) **external APIs** (mainly yfinance). AI features call the **Claude Code CLI (`claude -p`)** as a subprocess (Max subscription, no API key), plus one interactive chat using the **Claude Agent SDK**. Three background loops run inside the backend (weekly briefing, capture watcher, daily net-worth snapshot). The app has **231 API endpoints in 25 route groups**, **4 sidebar sections**, and is reachable as a PWA. It grew in many phases (v1 Streamlit → v2 React pages → v3 "pillars" → v4 redesign), which left **significant duplication, dead code, and several currently-broken AI features** (Section 13).

---

## 1. Context: who it's for and what it does

- **User:** one person (David). No multi-user, no auth.
- **Jobs the app serves today:**
  1. **Money** — net worth, investment portfolio analytics (very deep: optimisation, factors, tax, stress tests), cash flow / budgeting / reserve ("Notgroschen").
  2. **Personal admin** — a to-do tracker (`todos.json`) shared with a claude.ai chat project.
  3. **Projects & ventures** — project folders in the vault, an idea-validation pipeline, a personal-brand video pipeline, per-venture AI agents.
  4. **Research** — watchlist, AI stock-research reports, news captures from the iPhone, a weekly market brief.
  5. **AI assistant** — a voice "Jarvis" orb, a chat window, a catalogue of ~35–48 runnable AI skills.
- **Usage pattern:** laptop browser at `http://localhost:8000`; iPhone home-screen PWA was intended (see the problem in 13.1).

---

## 2. System diagram

```
                    ┌──────────────────────────── Windows laptop ────────────────────────────┐
 iPhone / iPad ───► │  :8000  FastAPI (uvicorn, pythonw, hidden; started at login by .vbs)   │
 (PWA, Tailscale/   │   ├─ /api/*   25 routers, 231 endpoints  ──► modules/* (business logic) │
  LAN — see 13.1)   │   ├─ /        serves frontend/dist (React SPA + service worker)         │
                    │   └─ lifespan loops: weekly briefing · capture watcher · daily snapshot │
 Browser ─────────► │                                                                        │
                    │  modules/* ──► core/config.py (all paths) ──► core/vault.py (.bak I/O)  │
                    │      │                                                                  │
                    │      ├─► OneDrive vault  C:\Users\david\OneDrive\David_Work_OS\         │
                    │      │     Markdown notes · Finance_Tracker.xlsx · todos.json · outputs │
                    │      ├─► repo data/   ledgers (jsonl/json/csv) · captures.db · caches   │
                    │      ├─► repo config/ *.yaml (buckets, peers, tax, targets, skills)     │
                    │      ├─► `claude -p` CLI subprocess  (all one-shot AI)                  │
                    │      ├─► Claude Agent SDK  (chat WebSocket only)                        │
                    │      ├─► Whisper (STT) · Piper (TTS) · Tesseract (OCR)  — all local     │
                    │      └─► yfinance · Ken French data · SEC EDGAR · Outlook iCal · GitHub │
                    │                                                                        │
                    │  Windows Task Scheduler: "Market Researcher" (Sun 18:00) — failing     │
                    └────────────────────────────────────────────────────────────────────────┘
   claude.ai project "Personal Admin" ──(OneDrive connector)──► edits the same todos.json
```

---

## 3. Tech stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12, FastAPI, uvicorn, pydantic, pandas, numpy |
| Finance libs | yfinance, PyPortfolioOpt, empyrical-reloaded, openpyxl (Excel), pdfplumber (TR statements) |
| AI | Claude Code CLI `claude -p` (subprocess, default model, Max subscription); `claude-agent-sdk` for chat |
| Local ML | OpenAI Whisper `base` (speech-to-text), Piper TTS (`en_GB-alan-medium`), Tesseract OCR (deu+eng) |
| Storage | OneDrive-synced Obsidian vault; repo `data/` (JSONL/JSON/CSV/SQLite/parquet); `config/*.yaml` |
| Frontend | React 18, TypeScript, Vite 5, Tailwind 3, TanStack Query 5, react-router 6, Recharts, Radix UI, zustand, framer-motion, react-three-fiber (3D orb) |
| PWA | `manifest.json` + custom service worker with per-build cache hash |
| Tests | pytest — 24 files, ~335 tests, almost all finance + to-dos |
| Leftovers | `streamlit`, `watchdog` still in `requirements.txt`; `.streamlit/` folder (Streamlit UI itself was deleted) |

---

## 4. Runtime, deployment and operations

- **Single server:** `backend/main.py` mounts all routers under `/api`, exposes `/health`, then serves `frontend/dist` (static assets + SPA catch-all with path-traversal guard). One process = whole app.
- **Start on login:** Startup-folder shortcut → `wscript launch_command_center.vbs backendonly` → hidden `_backend_only.bat` → `pythonw -m uvicorn backend.main:app --host 0.0.0.0 --port 8000`. Log: `%TEMP%\command_center_backend.log` (overwritten each start).
- **Desktop shortcut:** same `.vbs` without `backendonly`; opens `http://localhost:8000/today`.
- **Frontend deploys are manual:** source changes only appear after `npm run build` (or `smart_launch.bat`, the only script that rebuilds `dist`). `dist/` is gitignored.
- **Dev mode:** Vite on :5173 calling the backend directly (`VITE_API_BASE`, CORS). There is **no** Vite proxy (README claims one).
- **Other scripts (mostly superseded):** `start_dashboard.bat`, `start_backend.bat`, `start_frontend.bat` (dev), `run_daily_snapshot.bat` and `start_capture_watcher.bat` (replaced by lifespan loops), `run_market_researcher.bat` (Task Scheduler target), `install_autostart.bat`/`uninstall_autostart.bat`, two desktop-shortcut installers (v3 superseded by v4). Several use bare `python`, which is a broken Microsoft-Store stub on this machine.
- **Logging:** the backend never calls `logging.basicConfig`, so application `logger.info` lines are dropped; only warnings/errors and uvicorn output reach the log file. Background runs log to vault files.
- **Git:** private GitHub repo `personal-command-center`, 112 commits. Untracked clutter: `.path_update_backup_2026-10-25/` (stale copies of 26 `.py` files), `Command_Center_Build_Runbook.txt`, `HANDOFF_bucket_targets_v3.md`, `assets/design_inspiration/`.

---

## 5. Layer 1 — Data and sources of truth

### 5.1 OneDrive vault (`C:\Users\david\OneDrive\David_Work_OS\`)

Folder layout after the Oct-2026 restructure: `0 - Inbox`, `1 - Projects` (numbered sub-projects), `9 - Archive`, `99 - System`. Key files the app touches:

| Vault path | Role | Read/Write |
|---|---|---|
| `99 - System/Task_Command_Center.md` | Weekly task list (This week / Next week / Bigger items / Waiting for / hard dates) | R/W (tasks router, planner, briefing, voice) |
| `99 - System/Project_Index.md` | List of projects with status emoji | R |
| `99 - System/Templates/…` | Idea-validation and project templates | R |
| `1 - Projects/1 - Portfolio Management/1 - Finance Tracker/1 - Tracker/Finance_Tracker.xlsx` | Legacy Excel finance workbook (Bank, Transactions, Investments_TR, Investments_Crypto, Net_Worth, Income…) | R (app); W only by CLI parser + ad-hoc scripts |
| `…/2 - Investing/1 - Notes/{Watchlist, Hypothesis_Tracker, Investment_Philosophy, Anti_Portfolio}.md` | Investing notes; Watchlist.md is the watchlist source of truth | R/W |
| `…/2 - Investing/2 - Market Briefs/`, `3 - Stock Reports/<TICKER>/` | AI outputs (briefs; `.docx` + `.json` research reports) | W |
| `1 - Projects/5 - Personal Admin/5 - Routines/todos.json` | **Personal-admin to-dos (single source of truth)** — also edited by claude.ai | R/W (atomic) |
| `…/5 - Routines/1 - Background Runs/` | AI run logs, status, bootstrap scripts | W |
| `…/5 - Routines/2 - Briefings/`, `3 - Daily Todos/`, `4 - Week Planner/`, `5 - Weekly Reviews/` | Generated briefings / daily priorities / week plans | R/W |
| `1 - Projects/8 - Ideas/<idea>/` | Idea-validator stage outputs | W |
| `1 - Projects/4 - Career/…` | Evercore onboarding/technicals trackers; Personal Brand video folders | R/W |
| `0 - Inbox/News_Captures`, `Voice_Notes`, `Finance_Imports` | iPhone capture drop folders | R — **currently do not exist** |

Vault write rule (from CLAUDE.md): Python file I/O only, `.bak` before every write (OneDrive sync can corrupt editor-tool writes).

### 5.2 Repo `data/` (gitignored personal data)

| File | Domain | Notes |
|---|---|---|
| `transactions.jsonl` + `positions.json` | **Portfolio ledger — source of truth for holdings** | buy/sell/cash rows; FIFO cost basis |
| `realized_trades.csv`, `positions_daily.csv`, `networth_daily.csv` | Derived portfolio / net-worth series | rebuilt by snapshot/backfill |
| `cashflow_transactions.jsonl` + `cashflow_accounts.json`, `cashflow_{goal,reserve_target,expected_income,budget,reserve_balance}.json` | **Cash-flow ledger — source of truth for income/expenses** | entries are added by Claude in conversation; **no POST endpoint to add entries** |
| `networth_snapshots.json` | Monthly net-worth points (Excel + live captures) | legacy |
| `deployment_plans.jsonl`, `contribution_overrides.json`, `tax_carryforwards.json` | Portfolio planning / tax | some absent → defaults |
| `captures.db` (SQLite) | News/voice captures + `tasks`, `notes`, `park_queue` tables | 0 rows today |
| `price_cache/`, `fundamentals_cache/`, `ff_cache/` (parquet) | yfinance prices, company fundamentals (24 h), Fama-French factors | contains stray test tickers (A, B, C, D, TEST) |
| `checkpoints.jsonl`, `registry_state.json`, `weekly_briefing_state.json`, `daily_snapshot_state.json` | App state | briefing state still holds an old path |
| `finance_intake/*.py` | Ad-hoc one-off scripts (tracked in git) that write the Excel workbook | |
| `*.bak-YYYYMMDD_HHMMSS` | Manual backups from past sessions (not created by app code) | |

### 5.3 Repo `config/*.yaml`

`ticker_buckets.yaml` (ticker → bucket), `peer_overrides.yaml`, `etf_metadata.yaml` + `basiszins.yaml` (German Vorabpauschale tax), `networth_targets.yaml` (milestones), `import_profiles.yaml` (bank/Amex import), `skills_registry.yaml` (generated skill catalogue — rewritten at runtime, dirties git).

Constants in `core/config.py`: `BUCKET_TARGETS` (currently 49/21/24/6 — a pending handoff note asks for 50/30/20/0), drift bands, cash-flow category taxonomy, Notgroschen target, reserve split ratio, benchmarks, risk-free rate, `EVERCORE_START_DATE`.

### 5.4 External services

| Service | Used for | Auth |
|---|---|---|
| yfinance | prices, FX, fundamentals, news | none |
| Ken French data library | Fama-French factors | none |
| SEC EDGAR | filings for research | none |
| Outlook published iCal | calendar feed (planner) | `OUTLOOK_ICAL_URL` |
| GitHub API | recent commits (diagnostics only — no live UI) | `GITHUB_PAT`, `GITHUB_USERNAME` |
| Kraken | balance (diagnostics only) | `KRAKEN_API_KEY/SECRET` |
| Alpha Vantage | news sentiment (diagnostics only) | `ALPHA_VANTAGE_KEY` |
| Claude | all AI | Claude Code CLI login (Max). `ANTHROPIC_API_KEY` is loaded but unused |

Env vars present but read by no code: `TRADINGVIEW_API_KEY`, `WHOOP_*`, `YOUTUBE_API_KEY`, `FRED_API_KEY`, `ANTHROPIC_API_KEY`. Read by code but not set (defaults): `TODOS_FILE`, `INFO_BARRIER`, `RESTRICTED_TICKERS`, `TESSERACT_EXE`, `TESSERACT_TESSDATA_DIR`, `PICOVOICE_KEY`; frontend `VITE_API_BASE`.

### 5.5 Source-of-truth map

| Domain | Source of truth | Secondary / competing copies |
|---|---|---|
| Holdings, cost basis, realized P&L | `data/transactions.jsonl` + `positions.json` | Excel TR/Crypto sheets (still used by `/api/portfolio` and the briefing) |
| **Net worth** | **No single truth** — four figures (see 12.1) | |
| Income / expenses | `data/cashflow_transactions.jsonl` | Excel sheets via `/api/money/*`; unused `expenses.csv`/`income.csv` pipeline |
| Cash balances | **Split**: Excel Bank sheet vs `cashflow_accounts.json` | |
| Watchlist | vault `Watchlist.md` | deprecated `data/watchlist.json` (absent) |
| Personal-admin to-dos | vault `todos.json` | |
| Weekly tasks | vault `Task_Command_Center.md` | daily todos, week planner, project READMEs, captures DB (see 12.2) |
| Captures | `data/captures.db` | |
| Skill catalogue | `modules/agents/registry.py` | three other catalogues (see 12.3) |

---

## 6. Layer 2 — `core/` (shared foundation)

| File | Lines | Role |
|---|---|---|
| `core/config.py` | 363 | Every path constant, `.env` loading (`load_dotenv` at import), finance constants, info-barrier helpers (`info_barrier_active`, `restricted_tickers`, `is_restricted`), `set_env_var` (rewrites `.env`) |
| `core/markdown.py` | 376 | Tolerant parsers for vault conventions: section bullets, hard dates (EN+DE), Project_Index, reading list; add/toggle task by line |
| `core/vault.py` | 36 | `read_md`, `list_files`, `write_md` (`.bak` copy then write — not atomic), `append_to_inbox` |

---

## 7. Layer 3 — Business modules (`modules/`)

| Package | Size | What it does | Key reads → writes |
|---|---|---|---|
| **finance** | ~11.8k lines (largest) | Everything money — see 7.1 | ledgers, Excel, yfinance → `data/`, vault journals |
| **agents** | ~3k | Claude execution layer: `claude_cli.py` (`run_claude`), `background.py` (detached runs), `registry.py` (~48 skills), market researcher, research engine (9 skills), idea validator (12 stages), daily priorities, brand/career/equity/watchlist skills | vault notes → vault outputs, `Background Runs/` |
| **captures** | ~1k | iPhone Shortcut → inbox → OCR/Whisper → Claude enrichment → SQLite, with approval model (auto-approve ticker news; voice tasks pending) | `0 - Inbox/*` → `captures.db` |
| **briefings** | 280 | `context.py` assembles a snapshot (tasks, Excel portfolio, decisions, cash-flow alerts, projects, watchlist, latest brief); `weekly.py` writes the Sunday briefing | → `5 - Routines/2 - Briefings/` |
| **projects** | ~1k | Project folders: README milestones/next steps, project log, drafts, create project; per-venture agent manifests `_agents.json` | `1 - Projects/*` |
| **planner** | ~290 | Drag-and-drop week planner pooled from Task_Command_Center + project READMEs; calendar overlay; AI placement suggestions | → `4 - Week Planner/YYYY-Www.json` |
| **brand** | ~350 | Video idea folders (stage pipeline), inspirations board, edit-queue stub | `4 - Personal Brand/*` (video folder **missing** in vault) |
| **career** | 181 | Evercore onboarding + technicals checklists, career activity | `4 - Career/3 - Evercore/*` |
| **integrations** | ~380 | iCal, GitHub, Kraken, Alpha Vantage, travel (`Trips.md`), diagnostics | external APIs |
| **investing** | 108 | Per-ticker position notes; filters hypotheses/decisions/briefs by ticker | `Position Notes/` (missing) |
| **search** | 54 | Naive full-text search — scans the whole vault on every query, no index | vault |
| **system** | 97 | Reconciliation checkpoints | `data/checkpoints.jsonl` |
| **todos** | 293 | `todos.json` store: re-read → validate (status, 8 areas, priority 1–3, card-number guard) → backup → atomic write | vault `todos.json` |
| **tasks** | 0 | **Empty package** — task logic lives in `backend/api/tasks.py` (layering violation) | |
| **habits** | 48 | Health journal — **dead code**, never imported | |

### 7.1 Finance sub-domains (inside `modules/finance`)

- **A. Legacy Excel layer** — `loader.py` (only workbook reader), `money.py` (cash, net worth, monthly totals, runway, reserve, surplus split), `portfolio.py` (Excel holdings + yfinance), `networth_history.py`, `excel_import.py` (never run), `migrate_from_excel.py` (one-time), `tr_statement_parser.py` (Trade Republic PDF → writes Excel; CLI only).
- **B. Ledger portfolio analytics** — `positions.py` (truth), `price_history.py`, `realized.py`, `daily_snapshot.py`, `backfill.py`, `period_pnl.py`, `performance.py`, `risk.py`, `benchmarks.py`, `attribution.py` (Brinson), `capm_view.py`, `optimization.py` (frontier, Black-Litterman from Hypothesis_Tracker views), `factors.py` (FF3/FF5/momentum), `buckets.py` (4 buckets + drift), `decision_support.py` (sizing, rebalance, harvest, alerts), `capital_allocation.py`, `deployment_plans.py` (tranche plans), `forward_whatif.py`, `backtest.py`, `stress_tests.py`, `currency.py`, `dashboard.py`, `stock_detail.py`, `peers.py`, `watchlist.py`, `watchlist_analytics.py`, `diagnostics.py`.
- **C. German tax** — `tax.py`, `kap_form.py` (Anlage KAP), `verlustverrechnung.py` (loss pots), `vorabpauschale.py`, `tr_contributions.py`.
- **D. Cash-flow ledger** — `cashflow.py` (1,040 lines): monthly summary, overview, spending, recurring detection, needs-review queue, budget, reserve, runway, forecast, alerts.
- **E. Net Worth pillar** — `networth.py`: cash from `cashflow_accounts.json` + live-priced ledger holdings by bucket; milestones.
- **F. Vault journals & AI skills** — `decision_journal.py`, `anti_portfolio.py`, `hypothesis_review.py`, `portfolio_skills.py`, `money_skills.py`.

---

## 8. Layer 4 — HTTP API (`backend/api/`)

231 endpoints in 25 groups (full list in Appendix A). Routers are thin adapters over `modules/*`, except `tasks.py`, `inbox.py`, `home.py`, `planner.py`, `system.py` which contain logic directly.

| Group | # | Purpose | Live UI caller? |
|---|---|---|---|
| `/api/finance/*` | 86 | Ledger portfolio analytics, tax, optimisation, journal, deployment plans, net-worth snapshot | yes (Portfolio Hub, Portfolio workspace, Net Worth, Today) |
| `/api/cashflow/*` | 27 | Cash-flow ledger | yes (Cash Flow pillar, Today) |
| `/api/money/*` | 9 | Legacy Excel money layer | only Money workspace (URL-only) + one Cash Flow call |
| `/api/portfolio/*` | 3 | Legacy Excel holdings | Portfolio workspace |
| `/api/todos` | 5 | To-do tracker | yes |
| `/api/projects`, `/api/ideas` | 18 | Projects, venture agents, idea pipeline | yes |
| `/api/brand`, `/api/career` | 15 | Content studio; career | brand yes; **career no** |
| `/api/watchlist`, `/api/captures`, `/api/research` | 14 | Research & news | yes |
| `/api/skills`, `/api/runs` | 11 | AI skill launcher, background runs + WebSocket log stream | yes |
| `/api/chat/stream` | 1 | Agent SDK chat (WebSocket) | yes (`/chat` window) |
| `/api/voice/*` | 5 | Whisper, intent routing, Piper TTS, spoken briefing | yes (Jarvis orb) |
| `/api/system/*` | 7 | Status, config, cache, checkpoints, open file in OS, **read/write vault file** | yes (Settings) |
| `/api/tasks/*`, `/api/daily/*`, `/api/planner/*`, `/api/home/*`, `/api/inbox/*`, `/api/reading`, `/api/integrations/*`, `/api/search` | 34 | Task Command Center, daily priorities, week planner, old Home widgets, inbox, reading list, integrations, search | **mostly no** (only voice actions, search, diagnostics) — their pages were archived |

---

## 9. Layer 5 — AI layer

- **How Claude is called.** `modules/agents/claude_cli.run_claude(prompt, timeout, allowed_tools)` runs `claude -p` with the prompt on stdin; no `--model` flag (CLI default). Used by ~15 features. Chat (`/api/chat/stream`) uses `ClaudeSDKClient` with `setting_sources=[]`, read tools auto-approved, all other tools require an in-UI approval click, built-in Edit/Write on vault paths redirected to safe `vault_write`/`vault_append` tools.
- **Background runner** (`background.py`): writes a `<run_id>_bootstrap.py` into the vault, launches it detached, tracks `.log` / `.status.json` / `.meta.json`; cancel/restart via psutil; UI streams logs over a WebSocket. The newest run on disk is from 2026-06-06.

| Feature | Trigger | Output |
|---|---|---|
| Weekly briefing | lifespan loop, Sunday 18:00 | `2 - Briefings/YYYY-MM-DD_briefing.md` — **last success 2026-10-11** [verified] |
| Market Researcher | Windows Task Scheduler Sun 18:00, skill run, voice | weekly market brief + rewrites Hypothesis_Tracker — **wrong paths, task failing** [verified] |
| Research engine (9 skills: stock analysis, earnings, sector deep-dive, peers, valuation, macro, short thesis, insider scan, 13F) | Portfolio Hub → Research tab | `.docx` + `.json` per ticker in `3 - Stock Reports/` |
| Idea validator (12 stages) | Ideas page / idea workspace | `8 - Ideas/<idea>/` stage files, xlsx/docx/pptx |
| Venture agents | project workspace | per-venture outputs |
| Equity / watchlist / brand / career / portfolio / money skills (~35) | skill buttons in workspaces | run logs; some write vault files |
| Daily priorities | `/api/daily/today/generate` | `3 - Daily Todos/` — **no live UI caller** |
| Capture enrichment | capture watcher | `captures.db` — idle (inbox empty) |
| Voice "Jarvis" | header orb: briefing → TTS → mic → Whisper → Claude intent router → action (navigate, run skill, add task, add transaction, add hypothesis, capture) | |
| Planner AI, Excel-import categoriser | buttons / CLI | |

---

## 10. Layer 6 — Background jobs

| Job | Where | Schedule | State |
|---|---|---|---|
| Weekly briefing | lifespan loop (`modules/briefings/weekly.py`) | Sunday 18:00, checks every 30 min, catches up | **Failing** since Oct (retries every 30 min) |
| Capture watcher | lifespan loop (`modules/captures/watcher.py`) | every 60 s | Running but idle — inbox folders don't exist |
| Daily net-worth snapshot | lifespan loop (`modules/finance/snapshot_scheduler.py`) | daily 18:00 | **Working** (last run 2026-11-14) |
| Market Researcher | Windows Task Scheduler → `run_market_researcher.bat` | Sunday 18:00 | **Failing**: last result 0x80070002 (file not found), empty working directory [verified] |

---

## 11. Layer 7 — Frontend (`frontend/src`)

### 11.1 Navigation

| Sidebar group | Route | Page |
|---|---|---|
| overview | `/today` (default `/`) | Greeting, net worth / open to-dos / cash-flow-review tiles, due-soon + in-progress to-dos |
| finance | `/networth` | Donut by asset class, trend (1M–ALL), milestone, accounts hierarchy |
| finance | `/portfolio` | **Portfolio Hub**, 7 tabs: portfolio (KPIs, indexed performance, allocation vs target, deployment plans, decision alerts), holdings (positions, log/edit transactions, bucket reassignment), watchlist, captures, research, single stock, benchmarks |
| finance | `/cashflow` | 6 tabs: overview, spending, transactions, reserve & allocation, budget, forecast |
| planning | `/projects` | Project pillar cards, idea-pipeline summary, weekly briefing, new-project dialog |
| planning | `/todos` | To-do tracker grouped by priority, filters, edit dialog |
| system (collapsible) | `/background-runs`, search (⌘K), `/settings` | Run logs + skill catalogue; vault search; settings & diagnostics |
| off-sidebar | `/ideas`, `/brand`, `/decision-journal`, `/debug-jarvis` | reachable by link/URL |
| standalone (new tab) | `/workspace/portfolio` (13 tabs, the deepest finance UI), `/workspace/project/:id`, `/workspace/idea/:name`, `/workspace/brand/:id`, `/workspace/money` (legacy), `/workspace/watchlist/:ticker`, `/chat` | |
| legacy redirects | `/watchlist`, `/money`, `/inbox` → Portfolio Hub tabs | |

### 11.2 Shared layer

- **Design system:** `components/ui/*` (Radix-based primitives: panel, tag, button, dialog, select, tabs, toggle, task-check…). Theme = CSS variables in `globals.css`; **light default** ("Classic Elegance": warm off-white canvas, white panels, Dark Sea `#1F3D42` accent, Foghorn grey text, Camel warning, Windsor Wine danger), dark optional. Fonts: Inter (UI + tabular numbers), Cormorant Garamond (page titles), JetBrains Mono (code).
- **Layout:** `AppShell` = header (date + small Jarvis orb) + sidebar (4 groups) + content capped at 1200 px + toaster + update banner + ⌘K search palette + "ask Claude" dock (opens `/chat` window).
- **Data fetching:** `lib/api.ts` (`API_BASE = VITE_API_BASE || "http://localhost:8000"`), TanStack Query (30 s stale, retry 1, global error toast). Hooks per domain in `hooks/*` — `useFinance.ts` alone is 1,874 lines / 78 hooks.
- **PWA:** manifest + service worker (network-first navigation, cache-first assets, never caches `/api`), "new version available" banner.
- **Archive:** `src/_archive/` holds 10 retired v2 pages (home, plan, wealth, ventures, watchlist, system, inbox, money, career, reading).

### 11.3 Largest files

`hooks/useFinance.ts` 1,874 · `workspaces/money-workspace.tsx` 993 · `workspaces/portfolio-workspace.tsx` 988 · `hooks/usePortfolioHub.ts` 676 · `chat/chat-session.tsx` 675 · `charts/finance-analytics-charts.tsx` 669 · `portfolio/constraints-modal.tsx` 567 · `hooks/useJarvisBriefing.ts` 557 · `workspaces/project-workspace.tsx` 557 · `hooks/useCashflow.ts` 535 · `pages/todos.tsx` 534.

---

## 12. Overlap maps (the main structural debt)

### 12.1 Four net-worth figures and three cash sources
1. `money.latest_net_worth()` from **Excel** — called "authoritative" by `/api/money/snapshot`.
2. `networth_daily.csv` — daily snapshot: **bank cash from Excel** + ledger holdings at yfinance prices.
3. `networth.py` (Net Worth pillar, Today tile) — cash from **`cashflow_accounts.json`** + ledger holdings.
4. `networth_snapshots.json` — monthly Excel + live captures.
Docstrings state these disagree and are intentionally not reconciled. Cash balance comes from the Excel Bank sheet (home, snapshot, capital allocation) **or** `cashflow_accounts.json` (cash flow, net-worth pillar). The Notgroschen target exists in 4 places (config, `home.py`, persisted JSON, frontend constant).

### 12.2 Six task stores
`Task_Command_Center.md` (weekly tasks; used by planner, briefing, voice) · `todos.json` (personal admin; used by To-dos + Today only) · `3 - Daily Todos/*.md` (AI daily priorities; no live UI) · `4 - Week Planner/*.json` (assignments; no live UI) · project `README.md` "Next Steps" · `captures.db` `tasks`/`park_queue`. None of the AI features (briefing, voice, planner, daily priorities) read `todos.json`.

### 12.3 Four skill catalogues
`SKILL_REGISTRY` in `backend/api/skills.py` (~35, what actually runs) · `SKILL_DIRECTORY` (12, home quick-run) · `modules/agents/registry.py` `REGISTRY` (~48, the UI catalogue) · generated `config/skills_registry.yaml`. Some names exist in one but not another (e.g. `scenario_analyzer`, several voice skills) and would 404.

### 12.4 Two income/expense stacks and two holdings models
Excel (`/api/money/*`, Money workspace, briefing context) vs ledgers (`/api/cashflow/*`, `/api/finance/*`). The Cash Flow reserve tab still calls one legacy `/api/money` endpoint. The Portfolio workspace duplicates several Hub tabs.

---

## 13. Known problems (prioritised)

### 13.1 Broken right now
1. **All `claude -p` AI features fail** [verified]. The CLI refuses to start in the repo because of a malformed allow rule (line ~126) in `.claude/settings.local.json` (109 KB, 595 rules accumulated from past sessions). A manual run also reported an expired CLI OAuth session. Affected: weekly briefing, Market Researcher, research skills, idea validator, voice routing/briefing, venture agents, capture enrichment, planner AI. (Chat via the Agent SDK ignores local settings and may still work — unverified.)
2. **Market Researcher uses pre-restructure paths** [verified] (`Market_Briefs`, `Hypothesis_Tracker.md`, `Investment_Philosophy.md` at the `2 - Investing` root instead of `1 - Notes/` and `2 - Market Briefs/`) — it would read empty context and write orphan files. The briefing context imports the same wrong path. Its Windows task also fails (file not found) [verified].
3. **Phone/PWA cannot reach the API** [verified]: the production bundle hardcodes `http://localhost:8000`, so on an iPhone requests go to the phone itself. CORS also doesn't include the Tailscale `100.x` range.
4. **Info barrier (Evercore compliance) is not enforced** [verified]: `is_restricted()` is defined but never called; `/api/system/status` never returns `info_barrier`, so the banner never shows; the Settings toggle is a placeholder. Research skills run freely on any ticker.
5. Missing vault files/folders referenced by code: `Personal_Memory.md`, `Decision_Log.md`, `Command_Center_Checkpoints.md` (archived), `Idea_Decision_Criteria.md`, brand `Video Ideas/`, `Position Notes/`, `Decision Journal/`, inbox capture folders.

### 13.2 Security / safety risks
- Server listens on `0.0.0.0` with **no authentication**. Open to the LAN/tailnet: `PUT /api/system/file` (writes vault files), `POST /api/system/open` (`os.startfile` on vault paths), `POST /api/skills/{name}/run` (headless Claude with Bash/Write allowed).
- The chat WebSocket is reachable cross-site (CORS doesn't apply to WebSockets).
- Research engine and idea validator pre-allow `Write`/`Edit`/`Bash` for headless Claude inside the vault — contrary to the OneDrive write rule.
- Most `data/` ledgers are written with plain `write_text`: **no backup, not atomic** (positions, transactions, cash-flow ledger, CSVs, overrides). Only `todos.json`, deployment plans and peer overrides are atomic. `cashflow.clear_all()` deletes the ledger without backup (no caller).

### 13.3 Stale / inconsistent
- `CLAUDE.md` still describes a Streamlit app (`dashboard/app.py`, `streamlit run …`) and old `99_System\…` paths; "Agent SDK to be added later" (already used). `README.md` is similarly out of date (iPad-only, `start_dashboard.bat`, Vite proxy, old vault paths, Kraken/TradingView rows).
- Old path strings in runtime messages/prompts (`99_System/…`, `1_Projects/98_Ideen`, `03_Project_…`), hardcoded personal facts in prompts (a fixed net-worth figure, a fixed holdings list, the Evercore start date).
- ⌘K search palette omits Today, Net Worth, Cash Flow, To-dos. Some internal links use `<a href>` (full reload). Settings voice text mentions a retired "bottom bar". Chart and Jarvis colours are fixed hex (don't adapt to dark theme). `/api/system/config` reports the snapshot as "Windows Task Scheduler" (it's a lifespan loop).

### 13.4 Dead code / unused
- **Frontend:** `components/home/*` (11 files), `components/planner/*` (8) + `lib/planner.ts` + `@dnd-kit`, `components/calendar/*`, `cards/watchlist-card`, duplicate `finance/holdings-table`, `behavioral-nudges`, `optimization-signals`, `jarvis/briefing-overlay`, ~25 unused hooks (`useHome`, `useCareer`, `useReading`, `useInbox`, `useCalendar`…), unused deps `@radix-ui/react-checkbox`, `@react-three/drei`. URL-only pages: `/workspace/money`, `/workspace/watchlist/:ticker`, `/decision-journal`.
- **Backend:** `modules/habits`, `modules/projects/{ideas,templates,weekly_review,activity,journal}.py`, `excel_import.py` output, `trades.py`, Kraken/Alpha Vantage/GitHub (diagnostics only), daily-priorities + planner + home + career + reading + inbox endpoints with no live UI, duplicate Whisper loaders, empty `modules/tasks` and `skills/` folders, Streamlit leftovers.

### 13.5 Test coverage
Strong for finance analytics and to-dos (~335 tests). **Zero** tests for agents, `claude_cli`, background runner, chat, voice, schedulers, captures, integrations, cash-flow API routes beyond the module.

---

## 14. Open questions the redesign must answer (owner decides)

These are decisions, not facts — listed so the redesign conversation starts from them:

1. **Scope:** which of the five jobs (money, personal admin, projects/ventures, research, AI assistant) are core, and which can be retired or frozen?
2. **Finance truth:** should Excel be retired in favour of the ledgers (or vice versa)? What is *the* net-worth number and *the* cash balance?
3. **Tasks:** should the six task stores collapse into one (e.g. `todos.json`), and should the AI features (briefing, voice, planner) read it?
4. **AI execution:** keep `claude -p` subprocesses (Max subscription, fragile local config) or move to the Agent SDK / API for everything? One skill catalogue?
5. **Depth vs. use:** the portfolio analytics surface (86 endpoints, 13-tab workspace) — which parts are actually used weekly?
6. **Access:** phone usage — required? If yes, auth and network model (Tailscale only?) need designing.
7. **Compliance:** should the info barrier be enforced, and where?
8. **Automation:** which scheduled jobs matter (briefing, market research, snapshot, captures), and where should they run?
9. **Write safety:** one storage approach (atomic + backup) for all ledgers?

---

## Appendix A — Complete API route list (live, 231 endpoints)

### `/api/brand` (9)

```
GET     /api/brand
GET     /api/brand/all/{section}
POST    /api/brand/videos
GET     /api/brand/videos/{name}
POST    /api/brand/videos/{name}/skill
POST    /api/brand/videos/{name}/stage
GET     /api/brand/posting
GET     /api/brand/inspirations
POST    /api/brand/edits
```

### `/api/captures` (5)

```
GET     /api/captures
GET     /api/captures/radar
GET     /api/captures/for-ticker/{ticker}
GET     /api/captures/{capture_id}
POST    /api/captures/{capture_id}/route
```

### `/api/career` (6)

```
GET     /api/career
GET     /api/career/workspace
GET     /api/career/activity
GET     /api/career/model
POST    /api/career/checklist/toggle
POST    /api/career/skill
```

### `/api/cashflow` (27)

```
GET     /api/cashflow/categories
GET     /api/cashflow/months
GET     /api/cashflow/summary/{month}
GET     /api/cashflow/overview/{month}
GET     /api/cashflow/trend
GET     /api/cashflow/category-trend
GET     /api/cashflow/transactions/{month}
GET     /api/cashflow/reserve/{month}
GET     /api/cashflow/spending/{month}
GET     /api/cashflow/accounts
POST    /api/cashflow/accounts
DELETE  /api/cashflow/accounts/{name}
POST    /api/cashflow/reserve/{month}/balance
POST    /api/cashflow/config/reserve-target
GET     /api/cashflow/goal
POST    /api/cashflow/goal
GET     /api/cashflow/needs-review
POST    /api/cashflow/needs-review/{id}/resolve
GET     /api/cashflow/budget
POST    /api/cashflow/budget
GET     /api/cashflow/runway
GET     /api/cashflow/runway/scenarios
GET     /api/cashflow/forecast
GET     /api/cashflow/trends
GET     /api/cashflow/alerts/{month}
GET     /api/cashflow/config/expected-income
POST    /api/cashflow/config/expected-income
```

### `/api/chat` (1)

```
WS      /api/chat/stream
```

### `/api/daily` (5)

```
GET     /api/daily/today
POST    /api/daily/today/generate
POST    /api/daily/today/accept
POST    /api/daily/today/add
POST    /api/daily/today/toggle
```

### `/api/finance` (86)

```
GET     /api/finance/positions
POST    /api/finance/positions
PATCH   /api/finance/positions/{ticker}/bucket
GET     /api/finance/transactions
POST    /api/finance/transactions
PATCH   /api/finance/transactions/{id}
DELETE  /api/finance/transactions/{id}
GET     /api/finance/holdings
GET     /api/finance/holdings/pnl
GET     /api/finance/trades/realized
GET     /api/finance/prices/{ticker}
GET     /api/finance/returns/{ticker}
GET     /api/finance/performance
GET     /api/finance/performance/cumulative
GET     /api/finance/performance/rolling
GET     /api/finance/performance/sml
GET     /api/finance/performance/capm-decomposition
GET     /api/finance/performance/alpha-per-holding
GET     /api/finance/risk
GET     /api/finance/risk/correlation
GET     /api/finance/buckets
GET     /api/finance/optimization/frontier
GET     /api/finance/optimization/min-variance
GET     /api/finance/optimization/max-sharpe
GET     /api/finance/optimization/risk-parity
POST    /api/finance/optimization/black-litterman
GET     /api/finance/optimization/signals
POST    /api/finance/optimization/frontier-with-constraints
GET     /api/finance/optimization/distance-from-frontier
GET     /api/finance/factors/ff3
GET     /api/finance/factors/decomposition
GET     /api/finance/factors/ff5
GET     /api/finance/factors/momentum
GET     /api/finance/factors/rolling
GET     /api/finance/factors/loadings-comparison
POST    /api/finance/decisions/size
GET     /api/finance/decisions/rebalance
GET     /api/finance/decisions/harvest
GET     /api/finance/decisions/alerts
GET     /api/finance/decisions/hypotheses-view
GET     /api/finance/decisions/summary
POST    /api/finance/backtest/what-if
POST    /api/finance/backtest/market-shock
POST    /api/finance/backtest/fx-shock
POST    /api/finance/journal/decision
GET     /api/finance/journal/decisions
GET     /api/finance/journal/decision/{filename}
POST    /api/finance/journal/{filename}/retrospective
GET     /api/finance/journal/hit-rate
GET     /api/finance/journal/anti-portfolio
POST    /api/finance/journal/anti-portfolio
GET     /api/finance/watchlist/metrics
POST    /api/finance/watchlist/simulate-add
POST    /api/finance/tax/annual-estimate
GET     /api/finance/tax/holding-period/{ticker}
GET     /api/finance/tax/after-tax-return
GET     /api/finance/tax/kap-summary
GET     /api/finance/tax/loss-pots
GET     /api/finance/tax/loss-pots/carryforward
PUT     /api/finance/tax/loss-pots/carryforward
GET     /api/finance/tax/vorabpauschale
GET     /api/finance/capital-allocation/suggest
GET     /api/finance/currency/fx/{from_ccy}/{to_ccy}
GET     /api/finance/currency/breakdown
GET     /api/finance/currency/performance
GET     /api/finance/attribution/brinson
GET     /api/finance/stress/shocks
GET     /api/finance/stress/replay/{period_key}
GET     /api/finance/stress/replay-all
GET     /api/finance/portfolio/full-snapshot
GET     /api/finance/diagnostics
GET     /api/finance/dashboard/summary
GET     /api/finance/dashboard/performance-indexed
GET     /api/finance/stock-universe
GET     /api/finance/stock-detail/{ticker}
GET     /api/finance/peers/{ticker}
PATCH   /api/finance/peers/{ticker}
GET     /api/finance/benchmarks/compare
GET     /api/finance/deployment-plans
POST    /api/finance/deployment-plans
GET     /api/finance/deployment-plans/{plan_id}
PATCH   /api/finance/deployment-plans/{plan_id}
POST    /api/finance/deployment-plans/{plan_id}/tranches/{index}/execute
DELETE  /api/finance/deployment-plans/{plan_id}
POST    /api/finance/scenarios/forward-whatif
GET     /api/finance/networth/snapshot
```

### `/api/home` (6)

```
GET     /api/home/focus-areas
GET     /api/home/watchlist-signals
GET     /api/home/notgroschen
GET     /api/home/brain-system
GET     /api/home/manual-tasks
GET     /api/home/tasks-summary
```

### `/api/ideas` (9)

```
GET     /api/ideas
GET     /api/ideas/killed
POST    /api/ideas
GET     /api/ideas/{name}
POST    /api/ideas/{name}/run-stage
POST    /api/ideas/{name}/run-all
POST    /api/ideas/{name}/run-remaining
POST    /api/ideas/{name}/decide
POST    /api/ideas/{name}/overrides
```

### `/api/inbox` (3)

```
GET     /api/inbox
POST    /api/inbox/capture
POST    /api/inbox/{filename}/action
```

### `/api/integrations` (4)

```
GET     /api/integrations/calendar
GET     /api/integrations/github/commits
GET     /api/integrations/travel/upcoming
GET     /api/integrations/diagnostics
```

### `/api/money` (9)

```
GET     /api/money/snapshot
GET     /api/money/available-months
GET     /api/money/report/{month}
GET     /api/money/allocation/{month}
POST    /api/money/allocation/{month}/contribution-override
GET     /api/money/cashflow
GET     /api/money/categories
GET     /api/money/wealth-config
POST    /api/money/tax-scenario
```

### `/api/planner` (5)

```
GET     /api/planner/pool
GET     /api/planner/week/{iso_week}
POST    /api/planner/week/{iso_week}
POST    /api/planner/toggle
POST    /api/planner/ai-recommend/{iso_week}
```

### `/api/portfolio` (3)

```
GET     /api/portfolio
GET     /api/portfolio/performance
GET     /api/portfolio/allocations
```

### `/api/projects` (9)

```
GET     /api/projects
GET     /api/projects/briefing
GET     /api/projects/{project_id}
POST    /api/projects/{project_id}/log
POST    /api/projects/{project_id}/next-step/toggle
POST    /api/projects
GET     /api/projects/{project_id}/agents
POST    /api/projects/{project_id}/agents/{agent_key}/run
GET     /api/projects/{project_id}/runs
```

### `/api/reading` (1)

```
GET     /api/reading
```

### `/api/research` (5)

```
GET     /api/research/skills
GET     /api/research/reports
GET     /api/research/reports/latest/{ticker}
POST    /api/research/run
GET     /api/research/hypotheses
```

### `/api/runs` (5)

```
GET     /api/runs
GET     /api/runs/{run_id}
POST    /api/runs/{run_id}/cancel
POST    /api/runs/{run_id}/restart
WS      /api/runs/{run_id}/stream
```

### `/api/search` (1)

```
GET     /api/search
```

### `/api/skills` (6)

```
GET     /api/skills/status
GET     /api/skills
GET     /api/skills/registry
POST    /api/skills/registry/{key}/disable
POST    /api/skills/registry/{key}/enable
POST    /api/skills/{name}/run
```

### `/api/system` (7)

```
GET     /api/system/status
GET     /api/system/config
POST    /api/system/clear-cache
GET     /api/system/checkpoints
POST    /api/system/open
GET     /api/system/file
PUT     /api/system/file
```

### `/api/tasks` (5)

```
GET     /api/tasks
GET     /api/tasks/hard-dates
POST    /api/tasks/toggle
POST    /api/tasks/add
POST    /api/tasks/toggle-by-text
```

### `/api/todos` (5)

```
GET     /api/todos
POST    /api/todos
PATCH   /api/todos/{task_id}
PUT     /api/todos/{task_id}/subtasks/{index}
DELETE  /api/todos/{task_id}
```

### `/api/voice` (5)

```
GET     /api/voice/status
POST    /api/voice/transcribe
POST    /api/voice/route
POST    /api/voice/speak
POST    /api/voice/briefing
```

### `/api/watchlist` (4)

```
GET     /api/watchlist
POST    /api/watchlist
GET     /api/watchlist/{ticker}
POST    /api/watchlist/{ticker}/hypothesis
```

## Appendix B — Environment variable names (no values)

- Set in `.env`: `ANTHROPIC_API_KEY` (unused), `OUTLOOK_ICAL_URL`, `GITHUB_PAT`, `GITHUB_USERNAME`, `KRAKEN_API_KEY`, `KRAKEN_API_SECRET`, `ALPHA_VANTAGE_KEY`, `FRED_API_KEY` (unused), `TRADINGVIEW_API_KEY` (unused), `WHOOP_CLIENT_ID` / `WHOOP_CLIENT_SECRET` / `WHOOP_REFRESH_TOKEN` (unused), `YOUTUBE_API_KEY` (unused).
- Read by code, defaults apply: `TODOS_FILE`, `INFO_BARRIER` (auto/on/off), `RESTRICTED_TICKERS`, `TESSERACT_EXE`, `TESSERACT_TESSDATA_DIR`, `PICOVOICE_KEY`; frontend build-time `VITE_API_BASE`.

## Appendix C — Repository layout

```
personal_command_center/
├─ backend/            FastAPI app: main.py, api/ (25 routers incl. api/finance/), models/schemas.py, voice/piper/
├─ modules/            business logic (Section 7)
├─ core/               config.py · markdown.py · vault.py
├─ frontend/           Vite React app: src/{pages, components, hooks, lib, _archive}, public/{manifest.json, sw.js, icons}
├─ config/             *.yaml (buckets, peers, tax, targets, import profiles, skills registry)
├─ data/               personal ledgers, caches, SQLite (gitignored)
├─ tests/              pytest (24 files)
├─ docs/               this document
├─ *.bat / *.vbs       launchers, autostart, schedulers
└─ CLAUDE.md, README.md (both partly stale)
```
