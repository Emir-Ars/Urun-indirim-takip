"""Gerçek API veya veritabanı kullanmadan aynı ekranı test verisiyle gösterir."""

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT))

from app.ui.main import render_app  # noqa: E402
from ui_samples import SCENARIOS, preview_client  # noqa: E402

st.warning("Test verisi — gerçek fiyatlar değildir")
scenario = st.sidebar.selectbox("Test senaryosu", SCENARIOS, key="preview_scenario")
render_app(lambda: preview_client(scenario))
