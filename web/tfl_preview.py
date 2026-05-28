# web/tfl_preview.py
"""TFL 快速预览 — 纯 HTML/CSS 生成，无 Streamlit 依赖。"""
from __future__ import annotations
from html import escape
import pandas as pd

_BASE_CSS = """
<style>
.tfl-preview { font-family: 'Times New Roman', '宋体', serif; font-size: 10.5pt;
               max-width: 900px; margin: 0 auto; padding: 8px; }
.tfl-title   { font-size: 10pt; margin-bottom: 2px; }
.tfl-caption { font-size: 9pt; color: #555; margin-bottom: 6px; }
.tfl-table   { border-collapse: collapse; width: 100%; font-size: 10pt; }
.tfl-table thead tr:first-child th { border-top: 2px solid #000; border-bottom: none; }
.tfl-table thead tr:nth-child(2) th { border-top: 0.75px solid #000; }
.tfl-table thead tr:last-child  th { border-bottom: 1.5px solid #000; padding: 3px 6px; }
.tfl-table tbody tr:last-child  td { border-bottom: 2px solid #000; }
.tfl-table td, .tfl-table th    { border: none; padding: 2px 6px; vertical-align: top; }
.tfl-spacer td { height: 1px !important; padding: 0 !important; line-height: 0; font-size: 0; border: none !important; }
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
    tableno = escape(str(card.get("table no") or ""))
    title   = escape(str(card.get("title") or ""))
    pop     = escape(str(card.get("pop") or ""))
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
            lines.append(f"<div class='tfl-footnote'>{escape(fn)}</div>")
    return "".join(lines)


def _render_pstab(card: dict, datasets: dict) -> str:
    ds_name = str(card.get("Datasets") or "").strip()
    df = datasets.get(ds_name)

    trtlab = str(card.get("Trtlab") or "").strip()
    subgrp = str(card.get("Subgrp") or "").strip()
    varlab = escape(str(card.get("Varlab") or "指标").strip() or "指标")

    trt_cols = [escape(t.strip()) for t in trtlab.split("|")] if trtlab else ["数据列"]
    sub_cols = [escape(s.strip()) for s in subgrp.split("|")] if subgrp else []

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
            try:
                excluded = int(float(row.get("exclude") or 0)) == 1
            except (ValueError, TypeError):
                excluded = False
            if excluded:
                continue
            cur_class = row.get("Class")
            if prev_class is not None and cur_class != prev_class:
                n_cols = 1 + len(data_cols)
                body_html += f"<tr class='tfl-spacer'><td colspan='{n_cols}'></td></tr>"
            prev_class = cur_class

            try:
                order = int(float(row.get("Order") or 0))
            except (ValueError, TypeError):
                order = 0
            label = escape(str(row.get("Label") or ""))
            aval  = escape(str(row.get("Aval") or ""))

            if order == 0:
                label_cell = f"<td class='tfl-bold tfl-shaded'>{label}</td>"
                aval_class = "tfl-bold tfl-shaded"
            elif order == 1:
                label_cell = f"<td class='tfl-indent1'>{label}</td>"
                aval_class = "tfl-aval"
            else:
                label_cell = f"<td class='tfl-indent2'>{label}</td>"
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
    import re as _re
    list_df = datasets.get("list")
    badge = "<div class='tfl-badge'>📋 清单视图（横向A4模拟）</div>"

    if list_df is None or list_df.empty:
        content = _header_html(card) + badge + "<p style='color:#aaa;font-size:9pt'>（无 list 数据集）</p>"
        return _wrap(content)

    # 解析 ByseqL → byseq 数值（与 R 端 add_listing_to_doc 逻辑对齐）
    byseq_str = str(card.get("ByseqL") or "").strip()
    byseq = None
    if byseq_str:
        m = _re.search(r"\d+", byseq_str)
        if m:
            byseq = int(m.group())

    # 按 Byseq 筛选，未设置 ByseqL 时 fallback 展示全部
    if byseq is not None and "Byseq" in list_df.columns:
        try:
            rows = list_df[list_df["Byseq"].fillna(-1).astype(float).astype(int) == byseq]
        except (ValueError, TypeError):
            rows = list_df
        if "Byorder" in rows.columns:
            rows = rows.sort_values("Byorder")
    else:
        rows = list_df  # fallback：ByseqL 未填

    # 过滤 exclude=1
    if "exclude" in rows.columns:
        try:
            rows = rows[rows["exclude"].fillna(0).astype(float).astype(int) != 1]
        except (ValueError, TypeError):
            pass

    cols = [escape(str(r)) for r in rows.get("Lvalable", pd.Series()).tolist() if str(r).strip()]

    if not cols:
        hint = "（无列定义，请检查 ByseqL 值）" if byseq is None else f"（Byseq={byseq} 无匹配列）"
        content = _header_html(card) + badge + f"<p style='color:#aaa;font-size:9pt'>{hint}</p>"
        return _wrap(content)

    cols = cols[:15]

    # Values 字段作为示例数据行
    if "Values" in rows.columns:
        raw_vals = rows["Values"].fillna("").astype(str).tolist()[:15]
        example_vals = [escape(v) if v.strip() else "────" for v in raw_vals]
    else:
        example_vals = ["────"] * len(cols)

    header_row = "".join(f"<th style='background:#eee;font-size:9pt'>{c}</th>" for c in cols)
    ex_row = "".join(f"<td style='font-size:9pt;color:#666'>{v}</td>" for v in example_vals)
    empty_row = "".join(f"<td style='font-size:9pt;color:#ccc'>────</td>" for _ in cols)
    rows_html = f"<tr>{ex_row}</tr>" + "".join(f"<tr>{empty_row}</tr>" for _ in range(2))

    byseq_hint = f" (Byseq={byseq})" if byseq is not None else " ⚠️ ByseqL 未填"
    badge_full = f"<div class='tfl-badge'>📋 清单视图{escape(byseq_hint)}</div>"

    table_html = (
        f"<table class='tfl-table' style='font-size:9pt'>"
        f"<thead><tr>{header_row}</tr></thead>"
        f"<tbody>{rows_html}</tbody></table>"
    )
    content = _header_html(card) + badge_full + table_html + _footnotes_html(card)
    return _wrap(content)


_FIGURE_ICONS = {
    "KMplot": "📈", "Swimplot": "🏊", "WaterfallPlot": "📊",
    "Spiderplot": "🕷️", "Seriesplot": "📉", "Forestplot": "🌲",
}


def _render_figure(card: dict) -> str:
    macvar = str(card.get("MacVar") or "")
    trtlab = str(card.get("Trtlab") or "").strip()
    icon = _FIGURE_ICONS.get(macvar, "📊")
    placeholder = (
        f"<div class='tfl-placeholder'>"
        f"{icon}&nbsp;&nbsp;{escape(macvar)}（图形将在 R 端渲染）"
        f"</div>"
    )
    if trtlab:
        groups = " / ".join(escape(t.strip()) for t in trtlab.split("|"))
        placeholder += f"<div class='tfl-caption' style='margin-top:4px'>治疗组：{groups}</div>"
    badge = "<div class='tfl-badge'>📊 图形占位</div>"
    content = _header_html(card) + badge + placeholder + _footnotes_html(card)
    return _wrap(content)


def _render_mtext(card: dict) -> str:
    reftfl = escape(str(card.get("RefTFL") or "").strip())
    if reftfl:
        ref_html = (
            f"<p style='font-size:11pt'>格式同表 "
            f"<span style='color:#1a6091;font-weight:bold'>{reftfl}</span></p>"
            f"<p style='font-size:9pt;color:#888'>（在左侧导航树中找到该表查看结构）</p>"
        )
    else:
        ref_html = "<p style='color:#aaa'>（未设置 RefTFL）</p>"
    badge = "<div class='tfl-badge'>🔗 引用已有表格</div>"
    content = _header_html(card) + badge + ref_html + _footnotes_html(card)
    return _wrap(content)
