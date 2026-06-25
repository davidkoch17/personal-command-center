"""Central configuration: paths, env loading."""
import logging
from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()


def get_logger(name: str) -> logging.Logger:
    """Return a module logger (centralized so handlers can be tuned here later)."""
    return logging.getLogger(name)

VAULT_PATH = Path(r"C:\Users\david\OneDrive\David_Work_OS")
SYSTEM_PATH = VAULT_PATH / "99_System"
PROJECTS_PATH = VAULT_PATH / "1_Projects"
INBOX_PATH = VAULT_PATH / "0_Inbox"
READING_LIST_PATH = VAULT_PATH / "4_Areas" / "Learning" / "Reading_List.md"
TASKS_FILE = SYSTEM_PATH / "Task_Command_Center.md"
PROJECT_INDEX_FILE = SYSTEM_PATH / "Project_Index.md"

# --- Finance source file (read-only; single source of truth) ----------------
# All personal-finance analysis reads from this one workbook. Legacy banking /
# investment Excel files are NOT used.
FINANCE_TRACKER_FILE = (
    VAULT_PATH / "2_Personal" / "09_Finance Tracker" / "Finance Tracker" / "Finance_Tracker.xlsx"
)

# Generated data that lives in the repo (NOT the vault).
REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
WATCHLIST_FILE = DATA_DIR / "watchlist.json"

# --- Phase 15a finance foundation -------------------------------------------
# New sophisticated finance data layer (positions + transactions + price cache).
# All live in the repo's ``data/`` dir, NOT the vault, and are gitignored.
POSITIONS_FILE = DATA_DIR / "positions.json"
TRANSACTIONS_FILE = DATA_DIR / "transactions.jsonl"
PRICE_CACHE_DIR = DATA_DIR / "price_cache"

# --- Phase B: net worth + history -------------------------------------------
# Excel import drops live in the vault inbox; the parser maps them to the
# generated finance CSVs below. The CSVs (like positions.json/transactions.jsonl)
# live in the repo's ``data/`` dir, NOT the vault, written via Python file I/O.
FINANCE_IMPORTS_DIR = INBOX_PATH / "Finance_Imports"        # David drops Amex/bank .xlsx here
IMPORT_PROFILES_FILE = REPO_ROOT / "config" / "import_profiles.yaml"
EXPENSES_CSV = DATA_DIR / "expenses.csv"                    # date, amount_eur, category, source, raw_description, imported_from_file
INCOME_CSV = DATA_DIR / "income.csv"                        # date, amount_eur, source, raw_description
NETWORTH_DAILY_CSV = DATA_DIR / "networth_daily.csv"        # date, bank_total, portfolio_total_eur, crypto_total_eur, debts_total, net_worth_eur
POSITIONS_DAILY_CSV = DATA_DIR / "positions_daily.csv"      # date, ticker, qty, price_eur, value_eur, cost_basis_eur
REALIZED_TRADES_CSV = DATA_DIR / "realized_trades.csv"      # ticker, date_bought, date_sold, qty, buy_price_eur, sell_price_eur, fees_eur, realized_gain_eur, holding_days

# --- Phase A: capture pipeline (iOS Shortcut -> OneDrive inbox -> SQLite) -----
# Two iOS shortcuts drop a media file + sidecar JSON into these vault inbox
# folders; the polling watcher ingests them into the captures DB.
NEWS_CAPTURES_PATH = INBOX_PATH / "News_Captures"   # images / screenshots
VOICE_NOTES_PATH = INBOX_PATH / "Voice_Notes"       # voice notes
# SQLite is the source of truth for captures (filtering, status mutation,
# capture->many-tickers relations). Lives in the repo's data/ dir (NOT OneDrive),
# gitignored as per-machine personal data. Always written via Python (sqlite3).
CAPTURES_DB = DATA_DIR / "captures.db"
CAPTURE_WATCHER_INTERVAL_SECONDS = 60

# Tesseract OCR (deu+eng). The binary installs to Program Files; the German
# language pack lives in a user-writable tessdata dir (Program Files needs admin
# to write into). Both overridable via env for the second laptop / other setups.
TESSERACT_EXE = Path(
    os.getenv("TESSERACT_EXE", r"C:\Program Files\Tesseract-OCR\tesseract.exe")
)
TESSERACT_TESSDATA_DIR = Path(
    os.getenv("TESSERACT_TESSDATA_DIR", r"C:\Users\david\AppData\Local\Tesseract-OCR\tessdata")
)
TESSERACT_LANG = "deu+eng"

# Known projects Claude may tag a capture with (LOCKED in the v3 build spec § b).
CAPTURE_KNOWN_PROJECTS = ["K&E", "Ulli/Acebuche", "Immos", "Personal Brand"]

# Benchmark universe for performance/risk comparisons. Keys are stable handles;
# ``ticker`` is the yfinance symbol used to pull the benchmark return series.
BENCHMARKS: dict[str, dict[str, str]] = {
    "SPY": {"name": "S&P 500", "ticker": "^GSPC"},
    "MSCI_WORLD": {"name": "MSCI World", "ticker": "URTH"},
    "DAX": {"name": "DAX 40", "ticker": "^GDAXI"},
    "STOXX_600": {"name": "STOXX Europe 600", "ticker": "^STOXX"},
}
DEFAULT_BENCHMARK = "MSCI_WORLD"

# Four-bucket allocation framework — LOCKED in Investment_Philosophy.md § 0.
# Targets are fractions of total portfolio value. Drift thresholds + trigger
# alerts mirror the philosophy doc (Crypto > 30% trim, ETF < 45% rebalance).
BUCKET_TARGETS: dict[str, float] = {
    "etf_foundation": 0.49,
    "single_stocks": 0.21,
    "crypto": 0.24,
    "wild_cards": 0.06,
}
BUCKET_LABELS: dict[str, str] = {
    "etf_foundation": "ETF Foundation",
    "single_stocks": "Single Stocks",
    "crypto": "Crypto",
    "wild_cards": "Wild Cards",
}
# Drift bands (absolute percentage-point deviation from target): within ``ok`` is
# green, within ``warn`` is amber, beyond is red.
BUCKET_DRIFT_OK = 0.02   # ±2 pp
BUCKET_DRIFT_WARN = 0.05  # 2–5 pp

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# --- Investing / vault research paths ---------------------------------------
INVESTING_PATH = VAULT_PATH / "4_Areas" / "Investing"
HYPOTHESIS_TRACKER_FILE = INVESTING_PATH / "Hypothesis_Tracker.md"
WATCHLIST_UNIVERSE_FILE = INVESTING_PATH / "Watchlist.md"
INVESTMENT_PHILOSOPHY_FILE = INVESTING_PATH / "Investment_Philosophy.md"
MARKET_BRIEFS_DIR = INVESTING_PATH / "Market_Briefs"
POSITION_NOTES_DIR = INVESTING_PATH / "Position_Notes"
DECISION_LOG_FILE = SYSTEM_PATH / "Decision_Log.md"

# Career / brand workspace anchors.
CAREER_PATH = VAULT_PATH / "3_Career"
ONBOARDING_FILE = CAREER_PATH / "05_Current_Job" / "Onboarding.md"
CAREER_STRATEGY_PATH = CAREER_PATH / "06_Career_Strategy"
PERSONAL_MEMORY_FILE = SYSTEM_PATH / "Personal_Memory.md"
BRAND_PATH = PROJECTS_PATH / "05_Personal_Brand"
BRAND_VIDEOS_PATH = BRAND_PATH / "03_Video_Ideas"

# Default save target for generic tax scenarios (real-estate ones go to Immos, etc.).
STEUERN_SCENARIOS_PATH = VAULT_PATH / "2_Personal" / "03_Steuern" / "Scenarios"


# --- Info-barrier mode (Evercore) -------------------------------------------
# Once David starts at Evercore, personal investing in advised names/sectors is
# restricted. The dashboard dims those features. Auto-engages on the start date;
# can be forced on/off via the INFO_BARRIER env var (set from the Settings page).
EVERCORE_START_DATE = "2026-07-01"


def info_barrier_active() -> bool:
    """True if today is on/after Evercore start, or forced on via ``INFO_BARRIER``.

    ``INFO_BARRIER`` env values: ``on`` (force), ``off`` (force), ``auto`` (date-based).
    """
    from datetime import date

    mode = os.getenv("INFO_BARRIER", "auto").strip().lower()
    if mode == "on":
        return True
    if mode == "off":
        return False
    return date.today().isoformat() >= EVERCORE_START_DATE


def restricted_tickers() -> set[str]:
    """Names/tickers under an active advisory restriction (env ``RESTRICTED_TICKERS``).

    Comma-separated, upper-cased. Empty by default.
    """
    raw = os.getenv("RESTRICTED_TICKERS", "")
    return {t.strip().upper() for t in raw.split(",") if t.strip()}


def is_restricted(name: str | None) -> bool:
    """Whether a holding/ticker is restricted for personal research right now.

    Returns False unless the info-barrier is active. When active with an explicit
    ``RESTRICTED_TICKERS`` list, only listed names match. When active with NO list,
    everything is treated as restricted (compliance-safe default until David
    whitelists specific names).
    """
    if not info_barrier_active():
        return False
    listed = restricted_tickers()
    if not listed:
        return True
    nu = (name or "").upper()
    return any(tok in nu or nu in tok for tok in listed if nu)


def set_env_var(key: str, value: str) -> None:
    """Persist ``KEY=value`` to the repo ``.env`` and apply to the live process.

    Used by the Settings page (e.g. the info-barrier toggle). Rewrites an existing
    line or appends a new one; other lines are preserved.
    """
    env_path = REPO_ROOT / ".env"
    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    prefix = f"{key}="
    replaced = False
    for i, line in enumerate(lines):
        if line.strip().startswith(prefix):
            lines[i] = f"{key}={value}"
            replaced = True
            break
    if not replaced:
        lines.append(f"{key}={value}")
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.environ[key] = value
