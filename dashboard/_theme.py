"""Inject custom CSS and keyboard-shortcut JS into every Streamlit page."""
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

_CSS_PATH = Path(__file__).parent / "static" / "custom.css"
_JS_PATH = Path(__file__).parent / "static" / "shortcuts.js"


def inject_theme() -> None:
    """Inject the shared custom CSS, if present."""
    if _CSS_PATH.exists():
        css = _CSS_PATH.read_text(encoding="utf-8")
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def inject_shortcuts() -> None:
    """Inject the keyboard-shortcut JS via a zero-height component iframe.

    ``st.markdown`` strips ``<script>`` tags, so the JS is mounted inside a
    ``components.html`` iframe (which carries ``allow-same-origin``) where it can
    bind a keydown listener on the parent document and navigate the top window.
    """
    if _JS_PATH.exists():
        js = _JS_PATH.read_text(encoding="utf-8")
        components.html(f"<script>{js}</script>", height=0)
