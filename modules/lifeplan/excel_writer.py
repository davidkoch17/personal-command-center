"""„Als Basis übernehmen“: write inputs into the Excel's input cells.

Only the cells in ``inputs.CELL_MAP`` are touched — formulas, labels and
formatting stay as they are. A timestamped backup is taken first. The workbook
is loaded *with* formulas (never ``data_only=True``) so saving keeps them; Excel
is told to recalculate on open, since openpyxl cannot refresh cached values.
"""
from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from core.config import get_logger
from modules.lifeplan.inputs import LifePlanInputs, to_cells

logger = get_logger(__name__)


class ExcelLockedError(RuntimeError):
    """The workbook is open in Excel (Windows file lock)."""


def backup(xlsx: Path, backup_dir: Path | None = None) -> Path:
    """Copy ``xlsx`` to ``backup/<stem>_YYYYMMDD_HHMMSS.xlsx`` and return the path."""
    folder = backup_dir or xlsx.parent / "backup"
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = folder / f"{xlsx.stem}_{stamp}{xlsx.suffix}"
    n = 2
    while target.exists():
        target = folder / f"{xlsx.stem}_{stamp}_{n}{xlsx.suffix}"
        n += 1
    shutil.copy2(xlsx, target)
    return target


def write_inputs(xlsx: Path, inputs: LifePlanInputs, backup_dir: Path | None = None) -> dict:
    """Back up the workbook, then overwrite only the mapped input cells.

    Returns ``{"backup": str, "changed": [cell refs]}``. Raises
    ``ExcelLockedError`` if the file is open in Excel.
    """
    import openpyxl

    try:
        with open(xlsx, "r+b"):
            pass
    except PermissionError as exc:
        raise ExcelLockedError("Excel-Datei ist geöffnet – bitte schließen") from exc

    backup_path = backup(xlsx, backup_dir)
    wb = openpyxl.load_workbook(xlsx)  # keep formulas
    changed: list[str] = []
    for sheet, cell, value in to_cells(inputs):
        c = wb[sheet][cell]
        if isinstance(c.value, str) and c.value.startswith("="):
            # Safety net: the map must only ever point at input cells.
            raise ValueError(f"{sheet}!{cell} ist eine Formelzelle")
        if isinstance(value, float) and value.is_integer():
            value = int(value)
        if c.value != value:
            c.value = value
            changed.append(f"{sheet}!{cell}")
    wb.calculation.fullCalcOnLoad = True
    try:
        wb.save(xlsx)
    except PermissionError as exc:
        raise ExcelLockedError("Excel-Datei ist geöffnet – bitte schließen") from exc
    logger.info("lifeplan base written to %s (%d cells, backup %s)",
                xlsx, len(changed), backup_path.name)
    return {"backup": str(backup_path), "changed": changed}
