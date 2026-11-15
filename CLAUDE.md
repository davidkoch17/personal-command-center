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
- Optional: `session: true` = Task steht auf der "Working session"-Liste (oben im To-dos-Tab; Quick-Add legt Tasks direkt dort an). Fehlt das Feld, ist der Task nicht in der Session.
- Unbekannte Felder (auf Datei-, Task- und Subtask-Ebene) nie löschen.

### 2b. Erinnerungen und Screenshot-Import
- Fällige To-dos: jeden Abend 18:00 ein Push aufs iPhone via ntfy (`modules/todos/reminders.py`, Lifespan-Loop, holt verpasste Läufe beim nächsten Start nach). Inhalt: überfällig / heute / morgen / nächste 7 Tage, nur Titel + Datum. Konfig: `NTFY_TOPIC` (+ optional `NTFY_SERVER`) in `.env`; Status + Testknopf unter Settings → to-do reminders.
- Screenshot einfügen (Strg+V im To-dos-Tab, oder "from screenshot"): Claude liest das Bild (`modules/todos/screenshot.py`, `claude -p` mit Read-Tool) und schlägt Tasks vor; erst nach Bestätigung schreibt `store.create_tasks` alles in einem Schritt.

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

## Project overviews (`_overview.md`)

### 1. Wo und wofür
- Jeder Projektordner `1 - Projects\<Nr> - <Name>\` hat eine `_overview.md`. Sie ist die einzige Quelle für die Projektübersicht im Dashboard (`/projects`, `/projects/<Nr>`, Kachel auf `/today`).
- Gepflegt von David (Obsidian oder Dashboard) und Claude (Chat-Sessions, Claude Code). Projekt-ID im Dashboard = die Ordnernummer (`3`, auch `03` oder der volle Ordnername werden aufgelöst).
- Code: `modules/projects/overview.py` (Parser + Schreibfunktionen), API in `backend/api/projects.py`, Tests `python -m pytest tests/test_project_overview.py`.

### 2. Format
- YAML-Frontmatter: `project`, `status` (`active` | `waiting` | `paused` | `done`), `updated` (YYYY-MM-DD), `next_action`, `review_by` (YYYY-MM-DD).
- Abschnitte werden am Emoji in der `##`-Überschrift erkannt (Text daneben ist frei):
  - `## 🧭` Status — Freitext mit `**Was gerade läuft:**` und `**Nächste Aktion:**`.
  - `## ✅` Offen — `- [ ]` / `- [x]`, gruppiert unter fetten Zeilen `**Gruppe**`. ⏳ im Text = wartet auf jemanden.
  - `## 🕒` Letzte Aktivität — `- **DD.MM.** Text`, neueste zuerst.
  - `## 📝` Notizen & Entscheidungen — Freitext/Bullets (wird als Markdown gerendert).
  - `## 📂` Wo liegt was — Markdown-Tabelle; erste Spalte = Pfad relativ zum Projektordner (in Backticks), dann klickbar.
  - `## 💬` Updates — Eingangskorb: HTML-Kommentar, darunter freie Zeilen.
- Ein Abschnitt endet an der nächsten Überschrift oder an einer `---`-Linie (Footer). Fehlende Abschnitte/Datei = leer, kein Fehler.
- Dashboard-Flags: `stale` = letzte Aktivität UND neueste Dateiänderung älter als 21 Tage; `review_due` = `review_by` ≤ heute.

### 3. Schreibregeln
- Das Dashboard schreibt nur zwei Dinge: einen Haken unter ✅ umschalten und eine Zeile `- DD.MM. HH:MM – <Text>` unter 💬 anhängen. Jedes Mal: Datei frisch lesen → genau eine Zeile ändern → `updated` im Frontmatter setzen → `_overview.md.bak` anlegen → atomar schreiben (temp + replace). Zeilenenden bleiben erhalten.
- Claude schreibt die Dateien nur mit Python-I/O (nie Edit/Write-Tool, siehe Vault I/O rules), mit `.bak` vorher, frisch gelesen und gezielt geändert, nie aus einer alten Kopie.
- Davids Formulierungen nicht umschreiben; keine IBANs, Ausweis- oder Kontonummern.

### 4. Pflege durch Claude (am Ende jeder Session, die ein Projekt berührt)
- Status + `next_action` aktualisieren, Erledigtes abhaken und oben unter 🕒 eintragen, Entscheidungen unter 📝, `updated` setzen, `review_by` bei Bedarf weiterschieben.
- Zeilen unter 💬 Updates in Status / Offen / Aktivität einarbeiten und den Abschnitt danach leeren (den HTML-Kommentar stehen lassen).

## Global rule from David
When a task genuinely needs original creative thinking (David's voice, his principles, his strategy), STOP and tell David to think in Miro or OneNote first, then come back. Do not produce the creative output for him.

## Tech stack
Python 3.12+, Streamlit, pandas, python-frontmatter, python-dotenv, watchdog. Claude Agent SDK to be added later.

## Run
`streamlit run dashboard/app.py`
