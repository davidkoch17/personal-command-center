"""Declarative skills/agents registry (Phase C, item 3).

Builds and maintains ``config/skills_registry.yaml`` — the single declarative
catalogue of every skill + agent (name, domain, type, runner, schedule,
last_run). It composes:

* the in-app catalogue (``modules.agents.registry.REGISTRY``) for agents and the
  wealth/career/brand/system skills, and
* the nine Phase-C research skills (``modules.agents.skills.research.skills``),
  each of which runs in the background via the existing runner.

``last_run`` is stamped by :func:`stamp_last_run` after a successful research
run; the live last-run *health* still comes from the background-run status files
(``modules.agents.registry.list_entries``). The YAML is a repo file (NOT vault),
so normal Python file I/O is used.
"""
from __future__ import annotations

from datetime import datetime

import yaml

from core.config import SKILLS_REGISTRY_FILE, get_logger

logger = get_logger(__name__)

# cadence_days -> human schedule label for the YAML.
_SCHEDULE = {1: "daily", 7: "weekly", 30: "monthly", 90: "quarterly", 365: "yearly"}

# Research skills run via the generic launcher (POST /api/skills/<name>/run),
# which calls background.launch — the SAME runner infra as Idea Validation.
_RESEARCH_RUNNER = "background:modules.agents.skills.research.{callable}"


def _schedule_label(cadence_days: int | None) -> str:
    return _SCHEDULE.get(cadence_days, "on_demand") if cadence_days else "on_demand"


def _research_entries() -> list[dict]:
    from modules.agents.skills.research.skills import SKILLS

    entries = []
    for key, skill in SKILLS.items():
        schedule = "weekly" if key == "macro_brief" else "on_demand"
        entries.append({
            "name": key,
            "label": skill.label,
            "domain": "research",
            "type": "skill",
            "runner": _RESEARCH_RUNNER.format(callable=key),
            "target_kind": skill.target_kind,
            "schedule": schedule,
            "last_run": None,
        })
    return entries


def _inapp_entries() -> list[dict]:
    """Agents + non-research skills from the in-app registry."""
    from modules.agents import registry

    entries = []
    for e in registry.REGISTRY:
        if e["domain"] == "research" and e["key"] in {x["name"] for x in _research_entries()}:
            continue  # avoid double-listing research skills
        if e["run_skill"]:
            runner = f"skill:{e['run_skill']}"
        elif e["run_target"]:
            runner = f"page:{e['run_target']}"
        else:
            runner = "scheduled" if e["cadence_days"] else "manual"
        entries.append({
            "name": e["key"],
            "label": e["label"],
            "domain": e["domain"],
            "type": e["kind"],
            "runner": runner,
            "target_kind": e["prompt_arg"] or None,
            "schedule": _schedule_label(e["cadence_days"]),
            "last_run": None,
        })
    return entries


def build_entries() -> list[dict]:
    """The full declarative catalogue: research skills first, then everything else."""
    return _research_entries() + _inapp_entries()


def build_registry_yaml(preserve_last_run: bool = True) -> dict:
    """(Re)generate ``config/skills_registry.yaml``. Returns the written doc.

    Existing ``last_run`` timestamps are preserved across regenerations unless
    ``preserve_last_run`` is False.
    """
    prior = {}
    if preserve_last_run:
        prior = {e["name"]: e.get("last_run") for e in _load().get("skills", [])}

    entries = build_entries()
    for e in entries:
        if prior.get(e["name"]):
            e["last_run"] = prior[e["name"]]

    doc = {
        "_meta": {
            "description": "Declarative catalogue of every skill + agent (Phase C).",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "note": "Regenerate with modules.agents.skills.research.catalog.build_registry_yaml().",
        },
        "skills": entries,
    }
    SKILLS_REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
    SKILLS_REGISTRY_FILE.write_text(
        yaml.safe_dump(doc, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    logger.info("skills_registry.yaml regenerated (%d entries)", len(entries))
    return doc


def _load() -> dict:
    if not SKILLS_REGISTRY_FILE.exists():
        return {}
    try:
        return yaml.safe_load(SKILLS_REGISTRY_FILE.read_text(encoding="utf-8")) or {}
    except (yaml.YAMLError, OSError):
        logger.warning("skills_registry.yaml unreadable", exc_info=True)
        return {}


def load_entries() -> list[dict]:
    """Read the catalogue from disk (regenerating it if absent)."""
    doc = _load()
    if not doc.get("skills"):
        doc = build_registry_yaml()
    return doc.get("skills", [])


def stamp_last_run(name: str, status: str, on: datetime | None = None) -> None:
    """Record the last run of a skill into the YAML (best-effort, repo file I/O)."""
    doc = _load()
    if not doc.get("skills"):
        doc = build_registry_yaml()
    stamp = (on or datetime.now()).isoformat(timespec="seconds")
    for e in doc["skills"]:
        if e["name"] == name:
            e["last_run"] = {"at": stamp, "status": status}
            break
    else:
        return
    SKILLS_REGISTRY_FILE.write_text(
        yaml.safe_dump(doc, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
