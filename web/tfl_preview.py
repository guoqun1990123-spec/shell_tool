# web/tfl_preview.py
"""TFL 快速预览 — 纯 HTML/CSS 生成，无 Streamlit 依赖。"""
from __future__ import annotations
import pandas as pd

_BASE_CSS = """
<style>
.tfl-preview { font-family: 'Times New Roman', '宋体', serif; font-size: 10.5pt;
               max-width: 900px; margin: 0 auto; padding: 8px; }
.tfl-title   { font-size: 10pt; margin-bottom: 2px; }
.tfl-caption { font-size: 9pt; color: #555; margin-bottom: 6px; }
.tfl-table   { border-collapse: collapse; width: 100%; font-size: 10pt; }
.tfl-table thead tr:first-child th { border-top: 2px solid #000; border-bottom: none; }
.tfl-table thead tr:last-child  th { border-bottom: 1.5px solid #000; padding: 3px 6px; }
.tfl-table tbody tr:last-child  td { border-bottom: 2px solid #000; }
.tfl-table td, .tfl-table th    { border: none; padding: 2px 6px; vertical-align: top; }
.tfl-bold    { font-weight: bold; }
.tfl-indent1 { padding-left: 1.5em; }
.tfl-indent2 { padding-left: 3em; }
.tfl-aval    { color: #aaa; font-style: italic; }
.tfl-shaded  { background: #f5f5f5; }
.tfl-footnote{ font-size: 9pt; color: #333; margin-top: 4px; }
.tfl-placeholder { background: #eee; height: 280px; display: flex;
                   align-items: center; justify-content: center;
                   color: #888; font-size: 14pt; border-radius: 4px; }
.tfl-badge   { display: inline-block; background: #e8f4fd; color: #1a6091;
               padding: 2px 8px; border-radius: 10px; font-size: 8pt; margin-bottom: 6px; }
</style>
"""


def render_preview(card: dict, datasets: dict[str, pd.DataFrame]) -> str:
    """根据 MacVar 分支生成 HTML 预览字符串。"""
    macvar = str(card.get("MacVar") or "").strip()
    if macvar == "PStab":
        return _render_pstab(card, datasets)
    if macvar == "RptList":
        return _render_rptlist(card, datasets)
    if macvar == "mtext":
        return _render_mtext(card)
    if macvar in {"KMplot", "Swimplot", "WaterfallPlot",
                  "Spiderplot", "Seriesplot", "Forestplot"}:
        return _render_figure(card)
    return _wrap(_header_html(card) + "<p style='color:#888'>（未知 MacVar 类型）</p>")


# ── 内部工具 ──────────────────────────────────────────────────────────────────

def _wrap(body: str) -> str:
    return f"{_BASE_CSS}<div class='tfl-preview'>{body}</div>"


def _header_html(card: dict) -> str:
    tableno = card.get("table no") or ""
    title   = card.get("title") or ""
    pop     = card.get("pop") or ""
    return (
        f"<div class='tfl-caption'>表 {tableno}</div>"
        f"<div class='tfl-title'><b>{title}</b></div>"
        f"<div class='tfl-caption'>{pop}</div>"
    )


def _footnotes_html(card: dict) -> str:
    lines = []
    for i in range(1, 8):
        fn = str(card.get(f"footnote{i}") or "").strip()
        if fn:
            lines.append(f"<div class='tfl-footnote'>{fn}</div>")
    return "".join(lines)


def _render_pstab(card: dict, datasets: dict) -> str:
    ds_name = str(card.get("Datasets") or "").strip()
    df = datasets.get(ds_name)

    trtlab = str(card.get("Trtlab") or "").strip()
    subgrp = str(card.get("Subgrp") or "").strip()
    varlab = str(card.get("Varlab") or "指标").strip() or "指标"

    trt_cols = [t.strip() for t in trtlab.split("|")] if trtlab else ["数据列"]
    sub_cols = [s.strip() for s in subgrp.split("|")] if subgrp else []

    # ── 表头 HTML ──
    if sub_cols:
        header_html = "<thead>"
        header_html += "<tr>"
        header_html += f"<th rowspan='2'>{varlab}</th>"
        for trt in trt_cols:
            header_html += f"<th colspan='{len(sub_cols)}'>{trt}</th>"
        header_html += "</tr>"
        header_html += "<tr>"
        for _ in trt_cols:
            for sub in sub_cols:
                header_html += f"<th>{sub}</th>"
        header_html += "</tr></thead>"
        data_cols = [f"{t}_{s}" for t in trt_cols for s in sub_cols]
    else:
        header_html = "<thead><tr>"
        header_html += f"<th>{varlab}</th>"
        for trt in trt_cols:
            header_html += f"<th>{trt}</th>"
        header_html += "</tr></thead>"
        data_cols = trt_cols

    # ── 数据行 HTML ──
    body_html = "<tbody>"
    if df is None or df.empty:
        n_cols = 1 + len(data_cols)
        body_html += f"<tr><td colspan='{n_cols}' style='color:#aaa;text-align:center'>（无数据集）</td></tr>"
    else:
        prev_class = None
        for _, row in df.iterrows():
            if int(row.get("exclude") or 0) == 1:
                continue
            cur_class = row.get("Class")
            if prev_class is not None and cur_class != prev_class:
                n_cols = 1 + len(data_cols)
                body_html += f"<tr><td colspan='{n_cols}' style='height:6px'></td></tr>"
            prev_class = cur_class

            order = int(row.get("Order") or 0)
            label = str(row.get("Label") or "")
            aval  = str(row.get("Aval") or "")

            if order == 0:
                label_cell = f"<td class='tfl-bold tfl-shaded'>{label}</td>"
                aval_class = "tfl-bold tfl-shaded"
            else:
                indent_cls = "tfl-indent1" if order == 1 else "tfl-indent2"
                label_cell = f"<td class='{indent_cls}'>{label}</td>"
                aval_class = "tfl-aval"

            body_html += f"<tr>{label_cell}"
            for _ in data_cols:
                body_html += f"<td class='{aval_class}'>{aval if aval else '────'}</td>"
            body_html += "</tr>"

    body_html += "</tbody>"

    table_html = f"<table class='tfl-table'>{header_html}{body_html}</table>"
    badge = "<div class='tfl-badge'>⚡ 快速预览（非最终R输出）</div>"
    content = _header_html(card) + badge + table_html + _footnotes_html(card)
    return _wrap(content)


def _render_rptlist(card: dict, datasets: dict) -> str:
    return _wrap(_header_html(card) + "<p style='color:#888'>（RptList 预览占位）</p>")


def _render_mtext(card: dict) -> str:
    return _wrap(_header_html(card) + "<p style='color:#888'>（mtext 预览占位）</p>")


def _render_figure(card: dict) -> str:
    return _wrap(_header_html(card) + "<p style='color:#888'>（图形预览占位）</p>")
