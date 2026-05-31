# Personal Command Center

Local Streamlit dashboard for David. Reads his Obsidian vault from OneDrive; renders tasks, projects, finances, habits, and more.

## Vault location
`C:\Users\david\OneDrive\David_Work_OS\`

## Read these vault files for human context
- `99_System\Personal_Memory.md`
- `99_System\Project_Index.md`
- `99_System\Task_Command_Center.md`
- `99_System\Command_Center_Architecture.md`

## Code rules
- Python 3.12+, typed where reasonable.
- Small modules, single-responsibility functions, docstrings.
- No prints — use logging.
- Keep dashboard code in `dashboard/`. Business logic in `modules/`. Shared utilities in `core/`.

## Vault I/O rules (critical)
- When READING vault files: any approach is fine (Read tool, Python open, pandas, etc.).
- When WRITING vault files (any file inside `C:\Users\david\OneDrive\David_Work_OS\`):
  - Use Python file I/O ONLY. Do NOT use the Edit or Write tool.
  - Reason: Claude Code's Edit/Write tool has documented bugs with OneDrive sync (silent truncation, corruption). Python file I/O is safe.
  - Before any write, save a `.bak` copy of the target file.
- Files INSIDE this code repo can be edited via Edit/Write normally.

## Global rule from David
When a task genuinely needs original creative thinking (David's voice, his principles, his strategy), STOP and tell David to think in Miro or OneNote first, then come back. Do not produce the creative output for him.

## Tech stack
Python 3.12+, Streamlit, pandas, python-frontmatter, python-dotenv, watchdog. Claude Agent SDK to be added later.

## Run
`streamlit run dashboard/app.py`
