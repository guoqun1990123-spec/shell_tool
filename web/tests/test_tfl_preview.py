# web/tests/test_tfl_preview.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pandas as pd
from tfl_preview import render_preview, _BASE_CSS


def test_base_css_is_nonempty_string():
    assert isinstance(_BASE_CSS, str) and len(_BASE_CSS) > 0


def test_render_preview_unknown_macvar_returns_html():
    card = {"MacVar": "Unknown", "title": "Test", "table no": "1.1.1", "pop": "FAS"}
    html = render_preview(card, {})
    assert "<div" in html
