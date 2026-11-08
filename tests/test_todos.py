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


def test_unknown_id_raises_keyerror(todos_file):
    with pytest.raises(KeyError):
        store.update_task("missing", {"status": "done"})


def test_delete(todos_file):
    store.delete_task("konto")
    assert _read(todos_file)["tasks"] == []
