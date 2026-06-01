"""Shared UI helper for workspace skills (Phase 9b).

Every workspace exposes Claude-powered skills that must support both foreground
("Run now", blocking with a spinner) and background ("Run in background",
detached via :mod:`modules.agents.background`). This helper renders that control
pair consistently and stashes the foreground result in ``st.session_state``.

A skill is addressed by ``module_path`` + ``callable_name`` so the SAME reference
works for both modes: foreground imports and calls it; background hands it to
``background.launch``.
"""
from __future__ import annotations

import importlib
from typing import Any

import streamlit as st

from modules.agents import background
from core.config import get_logger

logger = get_logger(__name__)


def run_skill(
    label: str,
    module_path: str,
    callable_name: str,
    args: list[Any],
    *,
    key: str,
    allow_background: bool = True,
    spinner: str | None = None,
    render: bool = True,
) -> str | None:
    """Render a skill control (Run + optional background) and return its result.

    Foreground runs import ``module_path`` and call ``callable_name(*args)``; the
    string result is cached under ``st.session_state[f"skill_{key}"]`` and (if
    ``render``) shown as Markdown. Background runs launch a detached process and
    toast the run id. Returns the cached foreground result, or None.
    """
    result_key = f"skill_{key}"
    bg = st.checkbox("Run in background", key=f"{key}_bg") if allow_background else False
    if st.button(label, key=f"{key}_btn", type="primary"):
        if bg:
            try:
                info = background.launch(
                    module_path=module_path, callable_name=callable_name,
                    args=args, label=label,
                )
                st.toast(f"Started in background: {info['run_id']}", icon="🚀")
            except Exception as exc:  # noqa: BLE001
                logger.exception("background launch failed: %s", label)
                st.error(f"Could not launch in background: {exc}")
        else:
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
