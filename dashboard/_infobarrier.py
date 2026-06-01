"""Info-barrier UI helpers (Phase 9b).

Renders the compliance banners used on the Portfolio / Watchlist / Career
workspaces when :func:`core.config.info_barrier_active` is True. Logic lives in
``core.config``; this module only renders.
"""
from __future__ import annotations

import streamlit as st

from core import config


def global_banner() -> bool:
    """Show a page-level banner when the info-barrier is active. Returns active state."""
    if not config.info_barrier_active():
        return False
    listed = config.restricted_tickers()
    if listed:
        st.warning(
            "**Info-barrier active** (Evercore). Personal research is restricted on "
            f"flagged names: {', '.join(sorted(listed))}. Set `RESTRICTED_TICKERS` in `.env` to adjust."
        )
    else:
        st.warning(
            "**Info-barrier active** (Evercore). No `RESTRICTED_TICKERS` whitelist is set, "
            "so ALL names are treated as restricted (research actions locked). Add advised "
            "names to `RESTRICTED_TICKERS` in `.env`, or turn the barrier off in Settings."
        )
    return True


def restricted_notice(name: str) -> bool:
    """Show a per-name restriction banner if ``name`` is restricted. Returns restricted state."""
    if config.is_restricted(name):
        st.error(
            f"**Restricted — {name}.** Currently advising on a related transaction (or no "
            "whitelist set). Personal research actions (add hypothesis, build model) are locked."
        )
        return True
    return False
