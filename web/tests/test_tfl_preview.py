# web/tests/test_tfl_preview.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pandas as pd
from tfl_preview import render_preview, _BASE_CSS


def test_base_css_is_nonempty_string():
    assert isinstance(_BASE_CSS, str) and len(_BASE_CSS) > 0


def test_render_preview_unknown_macvar_returns_html():
    card = {"MacVar": "Unknown", "title": "Test Title", "table no": "1.1.1", "pop": "FAS"}
    html = render_preview(card, {})
    assert "<div" in html
    # header 应该出现且只出现一次（不重复）
    assert html.count("Test Title") == 1
    assert html.count("1.1.1") == 1


def test_render_preview_routes_all_macvar_types():
    for macvar in ["PStab", "RptList", "mtext", "KMplot", "Swimplot",
                   "WaterfallPlot", "Spiderplot", "Seriesplot", "Forestplot"]:
        card = {"MacVar": macvar, "title": "T", "table no": "1.1", "pop": "FAS"}
        html = render_preview(card, {})
        assert "<div" in html, f"MacVar={macvar} 应返回 HTML"
