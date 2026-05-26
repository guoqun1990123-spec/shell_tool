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
    return _wrap(_header_html(card) + "<p style='color:#888'>（未知 MacVar 类型）</p>", card)


# ── 内部工具 ──────────────────────────────────────────────────────────────────

def _wrap(body: str, card: dict) -> str:
    return f"{_BASE_CSS}<div class='tfl-preview'>{_header_html(card)}{body}</div>"


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
    return _wrap("<p style='color:#888'>（PStab 预览占位）</p>", card)


def _render_rptlist(card: dict, datasets: dict) -> str:
    return _wrap("<p style='color:#888'>（RptList 预览占位）</p>", card)


def _render_mtext(card: dict) -> str:
    return _wrap("<p style='color:#888'>（mtext 预览占位）</p>", card)


def _render_figure(card: dict) -> str:
    return _wrap("<p style='color:#888'>（图形预览占位）</p>", card)
