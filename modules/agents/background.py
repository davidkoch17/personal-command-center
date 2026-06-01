"""Detached background process runner for long skill/agent runs."""
import subprocess
import sys
import json
import os
import psutil
from pathlib import Path
from datetime import datetime
from core.config import VAULT_PATH


BG_LOG_DIR = VAULT_PATH / "99_System" / "Background_Runs"


def _ensure_dirs():
    BG_LOG_DIR.mkdir(parents=True, exist_ok=True)


def launch(module_path: str, callable_name: str, args: list, label: str) -> dict:
    """Launch a detached background Python process.

    Returns dict with run_id, pid, log_file, status_file.
    """
    _ensure_dirs()
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + label.replace(" ", "_")
    log_file = BG_LOG_DIR / f"{run_id}.log"
    status_file = BG_LOG_DIR / f"{run_id}.status.json"

    # Build a small bootstrap that imports + calls + writes status
    bootstrap = f"""
import json
import importlib
import sys
from datetime import datetime
from pathlib import Path

status_path = Path(r"{status_file}")

def write_status(s):
    status_path.write_text(json.dumps(s, indent=2, default=str), encoding="utf-8")

try:
    write_status({{"status": "running", "started_at": datetime.now().isoformat()}})
    module = importlib.import_module("{module_path}")
    func = getattr(module, "{callable_name}")
    result = func(*{json.dumps(args)})
    write_status({{"status": "completed", "completed_at": datetime.now().isoformat(), "result": str(result)[:500]}})
except Exception as e:
    import traceback
    write_status({{"status": "failed", "failed_at": datetime.now().isoformat(), "error": str(e), "traceback": traceback.format_exc()[:2000]}})
"""

    bootstrap_file = BG_LOG_DIR / f"{run_id}_bootstrap.py"
    bootstrap_file.write_text(bootstrap, encoding="utf-8")

    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS

    with open(log_file, "wb") as log:
        proc = subprocess.Popen(
            [sys.executable, str(bootstrap_file)],
            stdout=log,
            stderr=subprocess.STDOUT,
            creationflags=creationflags,
            close_fds=True,
        )

    info = {
        "run_id": run_id,
        "pid": proc.pid,
        "label": label,
        "log_file": str(log_file),
        "status_file": str(status_file),
        "launched_at": datetime.now().isoformat(),
    }
    return info


def get_status(run_id: str) -> dict:
    status_file = BG_LOG_DIR / f"{run_id}.status.json"
    if not status_file.exists():
        return {"status": "unknown"}
    return json.loads(status_file.read_text(encoding="utf-8"))


def list_recent_runs(limit: int = 20) -> list[dict]:
    if not BG_LOG_DIR.exists():
        return []
    status_files = sorted(BG_LOG_DIR.glob("*.status.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    out = []
    for f in status_files[:limit]:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            data["run_id"] = f.name.replace(".status.json", "")
            out.append(data)
        except Exception:
            continue
    return out


def is_alive(pid: int) -> bool:
    try:
        return psutil.pid_exists(pid)
    except Exception:
        return False
