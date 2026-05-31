"""Central configuration: paths, env loading."""
from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()

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

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
TRADINGVIEW_API_KEY = os.getenv("TRADINGVIEW_API_KEY", "")
