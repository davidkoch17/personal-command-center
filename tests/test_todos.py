"""Tests for modules.todos.store — the shared todos.json read/write layer."""
from __future__ import annotations

import json

import pytest

from modules.todos import store


@pytest.fixture
def todos_file(tmp_path, monkeypatch):
    path = tmp_path / "todos.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "updated": "2026-01-01",
                "owner_note": "keep me",
                "tasks": [
                    {
                        "id": "konto",
                        "title": "Konto kündigen",
                        "area": "Banking",
                        "priority": 1,
                        "status": "open",
                        "due": None,
                        "notes": "",
                        "custom": "chat-claude field",
                        "subtasks": [{"title": "Brief", "done": False, "priority": 1, "x": 1}],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(store, "TODOS_FILE", path)
    return path


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_update_preserves_unknown_fields_and_backs_up(todos_file):
    store.update_task("konto", {"status": "in_progress"})
    doc = _read(todos_file)
    assert doc["owner_note"] == "keep me"
    assert doc["updated"] != "2026-01-01"
    task = doc["tasks"][0]
    assert task["status"] == "in_progress"
    assert task["custom"] == "chat-claude field"
    backup = _read(todos_file.with_name("todos.backup.json"))
    assert backup["tasks"][0]["status"] == "open"


def test_write_rereads_file_first(todos_file):
    # Simulate chat-Claude adding a task between dashboard load and write.
    doc = _read(todos_file)
    doc["tasks"].append({"id": "extern", "title": "Extern", "status": "open", "priority": 2})
    todos_file.write_text(json.dumps(doc), encoding="utf-8")
    store.update_task("konto", {"notes": "hi"})
    ids = [t["id"] for t in _read(todos_file)["tasks"]]
    assert ids == ["konto", "extern"]


def test_create_generates_unique_slug(todos_file):
    a = store.create_task({"title": "Konto kündigen"})
    assert a["id"] == "konto-kuendigen"
    b = store.create_task({"title": "Konto kündigen"})
    assert b["id"] == "konto-kuendigen-2"


def test_subtask_merge_keeps_unknown_keys(todos_file):
    store.update_task(
        "konto",
        {"subtasks": [{"title": "Brief", "done": True}, {"title": "Anruf", "done": False}]},
    )
    subs = _read(todos_file)["tasks"][0]["subtasks"]
    assert subs[0] == {"title": "Brief", "done": True, "priority": 1, "x": 1}
    assert subs[1]["title"] == "Anruf"


def test_toggle_subtask(todos_file):
    store.set_subtask_done("konto", 0, True)
    assert _read(todos_file)["tasks"][0]["subtasks"][0]["done"] is True


def test_rejects_card_number_and_bad_values(todos_file):
    with pytest.raises(store.TodoError):
        store.update_task("konto", {"notes": "Karte 4111 1111 1111 1111"})
    with pytest.raises(store.TodoError):
        store.update_task("konto", {"status": "nope"})
    with pytest.raises(store.TodoError):
        store.update_task("konto", {"due": "morgen"})
    # Phone numbers and payee IBANs are fine.
    store.update_task("konto", {"notes": "Hotline +49 170 1234567"})
    store.update_task("konto", {"notes": "IBAN DE89 3704 0044 0532 0130 00"})


def test_priority_must_be_1_to_3(todos_file):
    for bad in (0, 4, "x"):
        with pytest.raises(store.TodoError):
            store.update_task("konto", {"priority": bad})
    with pytest.raises(store.TodoError):
        store.update_task("konto", {"subtasks": [{"title": "Brief", "priority": 5}]})
    store.update_task("konto", {"priority": 3})
    assert _read(todos_file)["tasks"][0]["priority"] == 3


def test_area_must_be_in_fixed_list(todos_file):
    for bad in ("Versicherungen", "", "banking"):
        with pytest.raises(store.TodoError):
            store.update_task("konto", {"area": bad})
    with pytest.raises(store.TodoError):
        store.create_task({"title": "X", "area": "Steuern"})
    store.update_task("konto", {"area": "Rechnungen"})
    assert _read(todos_file)["tasks"][0]["area"] == "Rechnungen"


def test_create_defaults_area_to_other(todos_file):
    assert store.create_task({"title": "Ohne Bereich"})["area"] == "Other"


def test_existing_invalid_values_dont_block_unrelated_edits(todos_file):
    # Legacy data (e.g. hand-edited by chat-Claude) only fails on the field
    # being changed, so a status toggle still works.
    doc = _read(todos_file)
    doc["tasks"][0]["area"] = "Steuern"
    doc["tasks"][0]["priority"] = 7
    todos_file.write_text(json.dumps(doc), encoding="utf-8")
    store.update_task("konto", {"status": "done"})
    assert _read(todos_file)["tasks"][0]["status"] == "done"


def test_unknown_id_raises_keyerror(todos_file):
    with pytest.raises(KeyError):
        store.update_task("missing", {"status": "done"})


def test_delete(todos_file):
    store.delete_task("konto")
    assert _read(todos_file)["tasks"] == []


# --- Working session, batch create ----------------------------------------------
def test_session_flag_set_and_cleared(todos_file):
    store.update_task("konto", {"session": True})
    assert _read(todos_file)["tasks"][0]["session"] is True
    store.update_task("konto", {"session": False})
    assert "session" not in _read(todos_file)["tasks"][0]


def test_create_tasks_batch_is_all_or_nothing(todos_file):
    created = store.create_tasks([{"title": "A"}, {"title": "B", "session": True}])
    assert [t["id"] for t in created] == ["a", "b"]
    assert _read(todos_file)["tasks"][-1]["session"] is True
    with pytest.raises(store.TodoError):
        store.create_tasks([{"title": "C"}, {"title": "D", "area": "Nope"}])
    assert [t["id"] for t in _read(todos_file)["tasks"]] == ["konto", "a", "b"]


# --- Reminders digest --------------------------------------------------------------
def test_digest_groups_and_formats():
    from datetime import date
    from modules.todos import reminders
    today = date(2026, 11, 14)
    tasks = [
        {"title": "Late", "status": "open", "due": "2026-11-10"},
        {"title": "Now", "status": "open", "due": "2026-11-14"},
        {"title": "Tmrw", "status": "waiting", "due": "2026-11-15"},
        {"title": "Week", "status": "open", "due": "2026-11-20"},
        {"title": "Far", "status": "open", "due": "2026-12-30"},
        {"title": "Done", "status": "done", "due": "2026-11-14"},
        {"title": "Undated", "status": "open", "due": None},
    ]
    g = reminders.build_digest(tasks, today)
    assert [i["title"] for i in g["overdue"]] == ["Late"]
    assert [i["title"] for i in g["today"]] == ["Now"]
    assert [i["title"] for i in g["tomorrow"]] == ["Tmrw"]
    assert [i["title"] for i in g["soon"]] == ["Week"]
    title, body = reminders.format_digest(g)
    assert "3 dringend" in title and "• Late (4d)" in body and "• Week (20.11.)" in body
    assert reminders.format_digest(reminders.build_digest([], today)) is None


# --- Screenshot import parsing ------------------------------------------------------
def test_screenshot_answer_parsing_and_cleaning():
    from modules.todos import screenshot
    answer = 'Here you go:\n```json\n[{"title": "Lampen kaufen", "area": "Wohnung", "priority": 5, ' \
             '"due": "2026-11-20", "subtasks": ["IKEA"], "done": false}, ' \
             '{"title": "", "area": "X"}, {"title": "Steuer", "area": "Steuern", "due": "morgen"}]\n```'
    items = [p for p in map(screenshot._clean, screenshot._parse_json_array(answer)) if p]
    assert items[0] == {"title": "Lampen kaufen", "area": "Wohnung", "priority": 3, "due": "2026-11-20",
                        "subtasks": [{"title": "IKEA", "done": False}], "done_in_image": False}
    assert items[1]["area"] == "Other" and items[1]["due"] is None and len(items) == 2
    with pytest.raises(store.TodoError):
        screenshot._parse_json_array("sorry, I can't read that")
    with pytest.raises(store.TodoError):
        screenshot.extract_todos("not-base64!!", "image/png")
