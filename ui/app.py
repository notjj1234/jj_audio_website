"""Streamlit entrypoint — multipage router."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC = _REPO_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

# Allow `from ui.common import ...` when Streamlit runs from repo root
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

st.set_page_config(page_title="Audio Tools", page_icon="🎸", layout="wide")

_pages = Path(__file__).parent / "pages"
pg = st.navigation(
    [
        st.Page(str(_pages / "isolate.py"), title="Audio Isolation", default=True),
        st.Page(str(_pages / "tab_pdf.py"), title="Audio → Tab PDF"),
    ]
)
pg.run()
