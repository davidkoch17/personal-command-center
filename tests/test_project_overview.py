"""Tests for modules.projects.overview — parser + the two surgical writers."""
from __future__ import annotations

import difflib
import os
import time
from datetime import date, datetime
from pathlib import Path

import pytest

from modules.projects import overview as ov

TODAY = date(2026, 11, 15)

SAMPLE = r"""---
project: Beispielprojekt
status: active
updated: 2026-11-01
next_action: Mit Anna telefonieren
review_by: 2026-11-10
---

# Beispielprojekt – Overview
↩ [[Home]]

> Intro-Text
> zweite Zeile

## 🧭 Status
**Was gerade läuft:** Vertrag wird geprüft.

**Nächste Aktion:** Anna anrufen.

## ✅ Offen
**🔴 Dringend**
- [ ] Vertrag unterschreiben
- [x] Angebot einholen

**Warten** (Detail: irgendwo)
- [ ] ⏳ Antwort von Bob
- [ ] **Fett:** mit Formatierung

## 🕒 Letzte Aktivität
- **15.11.** Angebot eingeholt
- **03.–04.10.** Zwei Tage gearbeitet
- **Juni** Start
- **20.12.** Letztes Jahr

## 📝 Notizen & Entscheidungen
- **Entscheidung:** kein Widerruf.

## 📂 Wo liegt was
| Ordner | Inhalt |
|---|---|
| `1 - Admin` | Verträge |
| `fehlt` | gibt es nicht |
| Reisen | [[Trips\|Trips]] (alt) |

## 💬 Updates
<!-- Schreib hier rein. -->

---
<sub>Footer</sub>
"""


@pytest.fixture()
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "1 - Projects"
    folder = root / "9 - Beispiel"
    (folder / "1 - Admin").mkdir(parents=True)
    (root / "Claude outputs").mkdir()
    (folder / "_overview.md").write_text(SAMPLE, encoding="utf-8", newline="")
    monkeypatch.setattr(ov, "PROJECTS_ROOT", root)
    monkeypatch.setattr(ov, "VAULT_ROOT", tmp_path)
    return folder


def _read(p: Path) -> str:
    with p.open("r", encoding="utf-8", newline="") as fh:
        return fh.read()


def _changed_lines(before: str, after: str) -> list[str]:
    return [
        l for l in difflib.unified_diff(before.splitlines(), after.splitlines(), lineterm="", n=0)
        if l[:1] in "+-" and not l.startswith(("+++", "---"))
    ]


# --- parser ------------------------------------------------------------------
def test_parse_frontmatter_and_sections(project: Path) -> None:
    data = ov.read_overview("9", today=TODAY)
    assert data["id"] == "9"
    assert data["name"] == "Beispielprojekt"
    assert data["status"] == "active"
    assert data["updated"] == "2026-11-01"
    assert data["review_by"] == "2026-11-10"
    assert data["status_section"]["current"] == "Vertrag wird geprüft."
    assert data["status_section"]["next_action"] == "Anna anrufen."
    assert "kein Widerruf" in data["notes_md"]
    assert data["updates"] == []
    assert data["intro"] == {"quote": ["Intro-Text", "zweite Zeile"], "nav": ["↩ [[Home]]"]}


def test_parse_open_items_groups_and_waiting(project: Path) -> None:
    items = ov.read_overview("9", today=TODAY)["open"]
    assert [i["text"] for i in items] == [
        "Vertrag unterschreiben", "Angebot einholen", "⏳ Antwort von Bob", "**Fett:** mit Formatierung",
    ]
    assert [i["checked"] for i in items] == [False, True, False, False]
    assert items[0]["group"] == "🔴 Dringend"
    assert items[2]["group"] == "Warten" and items[2]["group_note"] == "(Detail: irgendwo)"
    assert items[2]["waiting"] and not items[0]["waiting"]


def test_parse_activity_dates(project: Path) -> None:
    act = ov.read_overview("9", today=TODAY)["activity"]
    assert act[0] == {"date_raw": "15.11.", "date": "2026-11-15", "text": "Angebot eingeholt"}
    assert act[1]["date"] == "2026-10-04"  # range -> last day
    assert act[2]["date"] is None and act[2]["text"] == "Start"
    assert act[3]["date"] == "2025-12-20"  # future day/month -> previous year


def test_parse_files_table(project: Path) -> None:
    table = ov.read_overview("9", today=TODAY)["files_table"]
    assert table["headers"] == ["Ordner", "Inhalt"]
    assert table["rows"][0]["is_dir"] and table["rows"][0]["vault_path"] == "1 - Projects/9 - Beispiel/1 - Admin"
    assert table["rows"][1]["path"] is None
    assert table["rows"][2]["cells"] == ["Reisen", "[[Trips|Trips]] (alt)"]  # escaped pipe kept in cell


def test_parse_is_robust_to_garbage() -> None:
    for text in ["", "no frontmatter at all", "---\n: : bad yaml [\n---\n## ✅\n- [ ] x", "## random\ntext"]:
        data = ov.parse_overview(text, None, TODAY)
        assert isinstance(data["open"], list)
    assert ov.parse_overview("---\n: : bad yaml [\n---\n## ✅ Offen\n- [ ] x", None, TODAY)["open"][0]["text"] == "x"


def test_missing_overview_file(project: Path) -> None:
    (project.parent / "10 - Leer").mkdir()
    data = ov.read_overview("10", today=TODAY)
    assert data["exists"] is False and data["open"] == [] and data["name"] == "Leer"
    assert any(c["id"] == "10" for c in ov.list_projects(TODAY))


def test_project_id_resolution(project: Path) -> None:
    for pid in ("9", "09", "9 - Beispiel", "09_Beispiel"):
        assert ov.project_dir(pid) == project
    with pytest.raises(FileNotFoundError):
        ov.project_dir("42")


def test_cards_flags_and_sorting(project: Path) -> None:
    other = project.parent / "2 - Pausiert"
    other.mkdir()
    (other / "_overview.md").write_text(
        "---\nstatus: paused\nreview_by: 2026-12-31\n---\n## 🕒 Aktivität\n- **14.11.** x\n", encoding="utf-8"
    )
    cards = ov.list_projects(TODAY)
    assert [c["id"] for c in cards] == ["9", "2"]  # review due first
    c9 = cards[0]
    assert c9["review_due"] is True
    assert c9["open_count"] == 2 and c9["waiting_count"] == 1
    assert c9["last_activity"]["date_raw"] == "15.11."
    assert c9["stale"] is False
    assert all(c["id"] != "Claude outputs" for c in cards)


def test_stale_when_activity_and_files_old(project: Path) -> None:
    text = SAMPLE.replace("- **15.11.** Angebot eingeholt\n", "")
    (project / "_overview.md").write_text(text, encoding="utf-8")
    old = time.mktime(datetime(2026, 9, 1).timetuple())
    f = project / "1 - Admin" / "vertrag.pdf"
    f.write_text("x")
    os.utime(f, (old, old))
    card = next(c for c in ov.list_projects(TODAY) if c["id"] == "9")
    assert card["last_touch"] == "2026-10-04"
    assert card["stale"] is True


# --- recent files ------------------------------------------------------------
def test_recent_files_excludes(project: Path) -> None:
    keep = project / "1 - Admin" / "vertrag.pdf"
    keep.write_text("abc")
    for rel in ["!old/alt.md", ".obsidian/x.json", "a.md.bak", "b.bak-2026", "_bootstrap.py",
                ".status.json", "CacheClip/c.bin", "DaVinci Resolve Project Backups/p.drp", "x.status.json"]:
        p = project / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x")
    files = ov.recent_files("9")
    assert [f["rel_path"] for f in files] == ["1 - Admin/vertrag.pdf"]
    assert files[0]["size"] == 3
    assert ov.recent_files("9", limit=0) == []


# --- writers -------------------------------------------------------------------
def test_toggle_roundtrip_changes_only_that_line(project: Path) -> None:
    path = project / "_overview.md"
    before = _read(path)
    res = ov.toggle_item("9", 0, "Vertrag unterschreiben", today=TODAY)
    assert res["checked"] is True
    after = _read(path)
    assert sorted(_changed_lines(before, after)) == sorted([
        "-updated: 2026-11-01", "-- [ ] Vertrag unterschreiben",
        "+updated: 2026-11-15", "+- [x] Vertrag unterschreiben",
    ])
    assert (project / "_overview.md.bak").exists()
    assert _read(project / "_overview.md.bak") == before
    ov.toggle_item("9", "Vertrag unterschreiben", today=TODAY)
    assert _read(path) == before.replace("updated: 2026-11-01", "updated: 2026-11-15")


def test_toggle_by_text_with_formatting_and_index_mismatch(project: Path) -> None:
    # Stale index (as if Claude inserted a line meanwhile) -> falls back to the text.
    res = ov.toggle_item("9", 0, "**Fett:** mit Formatierung", today=TODAY)
    assert res["index"] == 3 and res["checked"] is True
    with pytest.raises(ov.OverviewError):
        ov.toggle_item("9", 0, "gibt es nicht", today=TODAY)


def test_append_update_inserts_one_line(project: Path) -> None:
    path = project / "_overview.md"
    before = _read(path)
    ov.append_update("9", "Payroll angerufen,\n warte auf Rückmeldung", now=datetime(2026, 11, 16, 9, 5))
    after = _read(path)
    assert _changed_lines(before, after) == [
        "-updated: 2026-11-01",
        "+updated: 2026-11-16",
        "+- 16.11. 09:05 – Payroll angerufen, warte auf Rückmeldung",
    ]
    lines = after.splitlines()
    assert lines[lines.index("<!-- Schreib hier rein. -->") + 1].startswith("- 16.11. 09:05")
    ov.append_update("9", "zweites", now=datetime(2026, 11, 16, 10, 0))
    data = ov.read_overview("9", today=TODAY)
    assert data["updates"] == [
        "- 16.11. 09:05 – Payroll angerufen, warte auf Rückmeldung", "- 16.11. 10:00 – zweites",
    ]
    assert "<sub>Footer</sub>" in _read(path).splitlines()[-1]
    with pytest.raises(ov.OverviewError):
        ov.append_update("9", "   ")


def test_writes_preserve_crlf(project: Path) -> None:
    path = project / "_overview.md"
    path.write_bytes(SAMPLE.replace("\n", "\r\n").encode("utf-8"))
    before = path.read_bytes()
    ov.toggle_item("9", 0, "Vertrag unterschreiben", today=TODAY)
    ov.toggle_item("9", 0, "Vertrag unterschreiben", today=TODAY)
    ov.append_update("9", "x", now=datetime(2026, 11, 1, 8, 0))
    after = path.read_bytes()
    assert b"\n" not in after.replace(b"\r\n", b"")
    assert after.replace("- 01.11. 08:00 – x\r\n".encode(), b"") == before
