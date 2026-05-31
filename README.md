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
