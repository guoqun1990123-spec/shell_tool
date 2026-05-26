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


def _make_pstab_card(trtlab="A组|B组|合计", subgrp=""):
    return {
        "MacVar": "PStab", "table no": "14.1.1",
        "title": "基线特征", "pop": "FAS",
        "Trtlab": trtlab, "Subgrp": subgrp,
        "Datasets": "t_demo",
        "footnote1": "FAS=全分析集", "footnote2": "",
    }


def _make_dataset():
    return pd.DataFrame([
        {"Class": 1, "Label": "年龄", "Order": 0, "Aval": "Mean (SD)", "exclude": 0, "BlankCol": ""},
        {"Class": 1, "Label": "年龄", "Order": 1, "Aval": "xx (xx.x)", "exclude": 0, "BlankCol": ""},
        {"Class": 2, "Label": "性别", "Order": 0, "Aval": "",           "exclude": 0, "BlankCol": ""},
        {"Class": 2, "Label": "男",   "Order": 1, "Aval": "xx (xx.x)", "exclude": 0, "BlankCol": ""},
        {"Class": 2, "Label": "跳过", "Order": 1, "Aval": "xx",        "exclude": 1, "BlankCol": ""},
    ])


def test_pstab_html_contains_table():
    card = _make_pstab_card()
    ds = {"t_demo": _make_dataset()}
    html = render_preview(card, ds)
    assert "<table" in html
    assert "tfl-table" in html


def test_pstab_excludes_excluded_rows():
    card = _make_pstab_card()
    ds = {"t_demo": _make_dataset()}
    html = render_preview(card, ds)
    assert "跳过" not in html


def test_pstab_trtlab_in_header():
    card = _make_pstab_card(trtlab="A|B|合计")
    ds = {"t_demo": _make_dataset()}
    html = render_preview(card, ds)
    assert "合计" in html


def test_pstab_double_header_with_subgrp():
    card = _make_pstab_card(trtlab="A|B", subgrp="男|女")
    ds = {"t_demo": _make_dataset()}
    html = render_preview(card, ds)
    assert html.count("<tr>") >= 2


def test_pstab_footnote_rendered():
    card = _make_pstab_card()
    ds = {"t_demo": _make_dataset()}
    html = render_preview(card, ds)
    assert "FAS=全分析集" in html


def test_pstab_missing_dataset_returns_html():
    card = _make_pstab_card()
    html = render_preview(card, {})
    assert "<div" in html
