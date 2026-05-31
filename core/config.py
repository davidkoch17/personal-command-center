"""Central configuration: paths, env loading."""
from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()

VAULT_PATH = Path(r"C:\Users\david\OneDrive\David_Work_OS")
SYSTEM_PATH = VAULT_PATH / "99_System"
PROJECTS_PATH = VAULT_PATH / "1_Projects"
INBOX_PATH = VAULT_PATH / "0_Inbox"

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
TRADINGVIEW_API_KEY = os.getenv("TRADINGVIEW_API_KEY", "")
