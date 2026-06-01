"""Helpers for rendering new-tab workspace links.

The deep-dive pattern (Phase 9): a sidebar page is an *overview* rendered in the
current tab; the working *workspace* opens in a NEW browser tab via an HTML
anchor with ``target="_blank"``. Workspace pages are hidden ``st.Page`` entries
registered in :mod:`dashboard.Home` with stable ``url_path`` values like
``workspace_project`` — so a link is just ``/workspace_<workspace>?id=<item>``.
"""
from __future__ import annotations

from urllib.parse import quote

import streamlit as st


def workspace_url(workspace: str, item_id: str | None = None) -> str:
    """Build the relative URL for a workspace page, id query-encoded."""
    url = f"/workspace_{workspace}"
    if item_id is not None and str(item_id) != "":
        url += f"?id={quote(str(item_id))}"
    return url


def workspace_link(
    label: str,
    workspace: str,
    item_id: str | None = None,
    key: str | None = None,  # noqa: ARG001 — kept for call-site symmetry
) -> None:
    """Render an emerald HTML anchor that opens the workspace in a new tab."""
    url = workspace_url(workspace, item_id)
    html = (
        f'<a href="{url}" target="_blank" '
        f'style="display:inline-block;padding:6px 12px;background:#047857;'
        f'color:white;text-decoration:none;border-radius:6px;font-weight:500;'
        f'font-size:0.85rem">{label}</a>'
    )
    st.markdown(html, unsafe_allow_html=True)
