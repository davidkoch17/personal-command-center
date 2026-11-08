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

## To-do-Tracker

### 1. Single Source of Truth
- Alle Personal-Admin-To-dos liegen in EINER Datei: `TODOS_FILE` aus `core/config.py`
  (= `OneDrive\David_Work_OS\1 - Projects\5 - Personal Admin\5 - Routines\todos.json`).
- Dieselbe Datei wird von drei Stellen bearbeitet: Dashboard (Browser, Tab `/todos` + `/today`), Claude Code (hier) und Chat-Claude im claude.ai-Projekt "Personal Admin" (über den OneDrive-Connector).
- Die Kopie in `4 - Health and Fitness\todos.json` ist veraltet und wird nicht benutzt.

### 2. Schema (version 1)
- Datei: `{ "version": 1, "updated": "YYYY-MM-DD", "tasks": [...] }`
- Task: `id` (slug), `title`, `area`, `priority` (1–3), `status` (`open` | `in_progress` | `waiting` | `done`), `due` (`YYYY-MM-DD` oder `null`), `notes`, `subtasks[ {title, done, priority?} ]`.
- Areas aktuell: Banking, Wohnung, Versicherung, Rechnungen, Business, Career, Investing, Other.
- Der Store erzwingt beides: `priority` (Task + Subtask) nur 1–3, `area` nur aus `AREAS` in `modules/todos/store.py` (neue Tasks ohne Area → `Other`). Neue Area = dort ergänzen; die UI-Auswahl kommt per API mit. Geprüft wird nur das gerade geänderte Feld, damit Altbestand einen Status-Toggle nie blockiert.
- Unbekannte Felder (auf Datei-, Task- und Subtask-Ebene) nie löschen.

### 3. Schreibregeln (gelten für jede Änderung, auch manuell)
- Immer über `modules/todos/store.py` schreiben (`create_task`, `update_task`, `set_subtask_done`, `delete_task`): Datei frisch lesen → gezielt ändern → Backup `todos.backup.json` → `updated` setzen → atomar schreiben.
- Nie aus einer In-Memory-Kopie überschreiben — Chat-Claude kann parallel ändern.
- Keine Kartennummern, Passwörter oder Freischaltcodes in die Datei. IBANs von Zahlungsempfängern sind erlaubt (der Store blockt Luhn-gültige Kartennummern, IBANs nicht).
- Nie mit dem Edit/Write-Tool an `todos.json` (siehe Vault I/O rules).

### 4. Arbeitsweise
- Wenn David hier sagt "neues To-do", "hak X ab" oder "Notiz zu Y", ändere `todos.json` direkt (über den Store).
- Erledigtes nicht löschen, sondern auf `status: "done"` setzen.
- Entscheidungen als done-Task mit Datum festhalten (z. B. "Entscheidungen 2026-11-08").
- Tests: `python -m pytest tests/test_todos.py`.

## Global rule from David
When a task genuinely needs original creative thinking (David's voice, his principles, his strategy), STOP and tell David to think in Miro or OneNote first, then come back. Do not produce the creative output for him.

## Tech stack
Python 3.12+, Streamlit, pandas, python-frontmatter, python-dotenv, watchdog. Claude Agent SDK to be added later.

## Run
`streamlit run dashboard/app.py`
