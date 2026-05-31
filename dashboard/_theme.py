"""Inject custom CSS and keyboard-shortcut JS into every Streamlit page."""
from pathlib import Path

import streamlit as st

_CSS_PATH = Path(__file__).parent / "static" / "custom.css"
_JS_PATH = Path(__file__).parent / "static" / "shortcuts.js"


def inject_theme() -> None:
    """Inject the shared custom CSS, if present."""
    if _CSS_PATH.exists():
        css = _CSS_PATH.read_text(encoding="utf-8")
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def inject_shortcuts() -> None:
    """Inject the keyboard-shortcut JS, if present."""
    if _JS_PATH.exists():
        js = _JS_PATH.read_text(encoding="utf-8")
        st.markdown(f"<script>{js}</script>", unsafe_allow_html=True)
