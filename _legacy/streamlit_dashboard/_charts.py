"""Plotly chart helpers — a consistent dark-emerald template across the app."""
from __future__ import annotations

import plotly.express as px
import plotly.graph_objects as go

EMERALD = "#047857"
EMERALD_LIGHT = "#10B981"
EMERALD_SEQUENCE = [EMERALD, EMERALD_LIGHT, "#34D399", "#6EE7B7", "#A7F3D0", "#059669"]


def _apply_layout(fig: go.Figure, title: str | None = None) -> go.Figure:
    """Apply the shared dark-emerald layout to any Plotly figure."""
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", size=13),
        title=dict(text=title or "", font=dict(size=15)),
    )
    return fig


def styled_pie(df, names, values, title: str | None = None) -> go.Figure:
    """Return an emerald-themed pie chart."""
    fig = px.pie(
        df, names=names, values=values,
        color_discrete_sequence=EMERALD_SEQUENCE,
    )
    _apply_layout(fig, title)
    fig.update_layout(showlegend=True)
    return fig


def styled_bar(df, x, y, title: str | None = None, orientation: str = "v",
               color: str | None = None) -> go.Figure:
    """Return an emerald-themed bar chart."""
    fig = px.bar(
        df, x=x, y=y, orientation=orientation, color=color,
        color_discrete_sequence=EMERALD_SEQUENCE,
    )
    _apply_layout(fig, title)
    return fig


def styled_line(df, x, y, title: str | None = None, color: str | None = None) -> go.Figure:
    """Return an emerald-themed line chart."""
    fig = px.line(
        df, x=x, y=y, color=color, markers=True,
        color_discrete_sequence=EMERALD_SEQUENCE,
    )
    _apply_layout(fig, title)
    return fig
