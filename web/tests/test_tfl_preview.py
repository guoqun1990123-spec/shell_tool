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


# ── RptList ──
def test_rptlist_html_contains_table():
    card = {"MacVar": "RptList", "table no": "16.2.1", "title": "受试者清单",
            "pop": "FAS", "Datasets": "l_subj"}
    list_df = pd.DataFrame([
        {"ListName": "l_subj", "Byseq": 1, "Byorder": 1,
         "Lvalable": "受试者号", "Values": "", "Merge": "", "exclude": 0},
        {"ListName": "l_subj", "Byseq": 2, "Byorder": 2,
         "Lvalable": "访视",    "Values": "", "Merge": "", "exclude": 0},
        {"ListName": "l_subj", "Byseq": 3, "Byorder": 3,
         "Lvalable": "跳过",    "Values": "", "Merge": "", "exclude": 1},
    ])
    html = render_preview(card, {"list": list_df})
    assert "<table" in html
    assert "受试者号" in html
    assert "跳过" not in html


# ── 图形 ──
def test_figure_html_shows_placeholder():
    for macvar in ["KMplot", "Swimplot", "WaterfallPlot",
                   "Spiderplot", "Seriesplot", "Forestplot"]:
        card = {"MacVar": macvar, "title": "KM曲线", "table no": "14.2.1",
                "pop": "FAS", "Trtlab": "A|B"}
        html = render_preview(card, {})
        assert "tfl-placeholder" in html
        assert macvar in html


# ── mtext ──
def test_mtext_shows_reftfl():
    card = {"MacVar": "mtext", "title": "格式同表", "table no": "14.2.2",
            "pop": "", "RefTFL": "14.1.1"}
    html = render_preview(card, {})
    assert "14.1.1" in html


def test_mtext_empty_reftfl():
    card = {"MacVar": "mtext", "title": "格式同表", "table no": "14.2.2",
            "pop": "", "RefTFL": ""}
    html = render_preview(card, {})
    assert "<div" in html
