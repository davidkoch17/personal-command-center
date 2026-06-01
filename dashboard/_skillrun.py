"""Shared UI helper for workspace skills (Phase 9b, updated Phase 10a).

Every workspace exposes Claude-powered skills. Phase 10a forces all skill runs
to **background** mode by default — there is no "Run in background" checkbox and
no blocking spinner. A skill is addressed by ``module_path`` + ``callable_name``
and handed to :func:`modules.agents.background.launch`; progress and output land
on the Background Runs page.

The exception is fast, interactive skills that genuinely need a synchronous
answer (e.g. a short "Ask Claude" query or a quick local vault write). Those pass
``synchronous=True`` and run inline with a clear timeout; on timeout the caller
falls back to background.
"""
from __future__ import annotations

import importlib
from typing import Any

import streamlit as st

from modules.agents import background
from core.config import get_logger

logger = get_logger(__name__)

_BG_TOAST = (
    "Started in background — see Background Runs page or check vault output "
    "folder when complete."
)


def run_skill(
    label: str,
    module_path: str,
    callable_name: str,
    args: list[Any],
    *,
    key: str,
    synchronous: bool = False,
    spinner: str | None = None,
    render: bool = True,
) -> str | None:
    """Render a skill Run button.

    Default (background): pressing the button launches a detached process and
    toasts. Returns None.

    ``synchronous=True``: for fast/interactive skills (short queries, quick local
    writes). Imports ``module_path`` and calls ``callable_name(*args)`` inline,
    caches the result under ``st.session_state[f"skill_{key}"]`` and (if
    ``render``) shows it as Markdown.
    """
    result_key = f"skill_{key}"

    if not synchronous:
        if st.button(label, key=f"{key}_btn", type="primary"):
            try:
                background.launch(
                    module_path=module_path, callable_name=callable_name,
                    args=args, label=label,
                )
                st.toast(_BG_TOAST)
            except Exception as exc:  # noqa: BLE001
                logger.exception("background launch failed: %s", label)
                st.error(f"Could not launch in background: {exc}")
        return None

    # Synchronous path — fast / interactive skills only.
    if st.button(label, key=f"{key}_btn", type="primary"):
        with st.spinner(spinner or f"{label}…"):
            try:
                mod = importlib.import_module(module_path)
                fn = getattr(mod, callable_name)
                st.session_state[result_key] = fn(*args)
            except Exception as exc:  # noqa: BLE001
                logger.exception("skill failed: %s", label)
                st.error(f"{label} failed: {exc}")
    resp = st.session_state.get(result_key)
    if resp and render:
        st.markdown(resp if isinstance(resp, str) else str(resp))
    return resp
