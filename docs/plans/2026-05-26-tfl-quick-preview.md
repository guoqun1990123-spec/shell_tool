# TFL 快速预览 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在卡片 level1 视图中嵌入「👁️ 预览」标签页，用纯 HTML/CSS 模拟各类 TFL 外观，并提供「🔄 用R真实渲染」按钮下载单表 docx。

**Architecture:** 新建 `web/tfl_preview.py` 负责所有 HTML 生成逻辑（纯函数，无 Streamlit 依赖），按 MacVar 分支渲染。`config_editor.py` 的 `_render_level1` 末尾将「展开更多」expander 包裹进 `st.tabs(["✏️ 编辑", "👁️ 预览"])`，预览 tab 调用 `tfl_preview.render_preview()`。切换选中行时（`_render_level1` 被调用时）自动触发预览，字段修改后需手动点「⚡ 刷新预览」按钮。

**Tech Stack:** Python 3, Streamlit 1.57, pandas。纯 HTML/CSS 字符串生成，无额外依赖。

---

## 背景速查

| 文件 | 作用 |
|------|------|
| `web/config_editor.py:342` | `_render_level1` — 需在末尾加预览 tab |
| `web/config_editor.py:508` | 「展开更多」expander — 移入「编辑」tab |
| `web/renderer.py` | `run_preview(card, datasets)` — 真实渲染复用 |
| `web/schema.py` | `VALID_MACVAR`, `DATASET_TABLE_COLS` |

MacVar 类型分类：
- **表格**：`PStab`
- **清单**：`RptList`
- **图形**：`KMplot`, `Swimplot`, `WaterfallPlot`, `Spiderplot`, `Seriesplot`, `Forestplot`
- **引用**：`mtext`

---

## Task 1：新建 `tfl_preview.py` — 骨架 + 公共 CSS

**Files:**
- Create: `web/tfl_preview.py`
- Create: `web/tests/test_tfl_preview.py`

**Step 1: 写失败测试**

```python
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
```

**Step 2: 运行测试确认失败**

```bash
cd web && python -m pytest tests/test_tfl_preview.py -v
```
预期：`ModuleNotFoundError: No module named 'tfl_preview'`

**Step 3: 创建 `tfl_preview.py` 骨架**

```python
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
```

**Step 4: 运行测试确认通过**

```bash
cd web && python -m pytest tests/test_tfl_preview.py -v
```
预期：2 PASSED

**Step 5: Commit**

```bash
git add web/tfl_preview.py web/tests/test_tfl_preview.py
git commit -m "feat(web): add tfl_preview module skeleton with base CSS"
```

---

## Task 2：PStab HTML 渲染

**Files:**
- Modify: `web/tfl_preview.py` — 实现 `_render_pstab`
- Modify: `web/tests/test_tfl_preview.py` — 添加测试

**Step 1: 写失败测试**

在 `test_tfl_preview.py` 末尾追加：

```python
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
    # 双行表头：第一行包含治疗组，第二行包含子组
    assert html.count("<tr>") >= 2


def test_pstab_footnote_rendered():
    card = _make_pstab_card()
    ds = {"t_demo": _make_dataset()}
    html = render_preview(card, ds)
    assert "FAS=全分析集" in html


def test_pstab_missing_dataset_returns_html():
    card = _make_pstab_card()
    html = render_preview(card, {})  # 没有 dataset
    assert "<div" in html
```

**Step 2: 运行测试确认失败**

```bash
cd web && python -m pytest tests/test_tfl_preview.py::test_pstab_html_contains_table -v
```
预期：FAIL（占位符版本不含真实 `<table`）

**Step 3: 实现 `_render_pstab`**

用以下代码替换 `tfl_preview.py` 中的 `_render_pstab` 占位实现：

```python
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
        # 双行表头
        header_html = "<thead>"
        # 第一行：指标列 + 每个治疗组跨子组列数
        header_html += "<tr>"
        header_html += f"<th rowspan='2'>{varlab}</th>"
        for trt in trt_cols:
            header_html += f"<th colspan='{len(sub_cols)}'>{trt}</th>"
        header_html += "</tr>"
        # 第二行：子组标签
        header_html += "<tr>"
        for _ in trt_cols:
            for sub in sub_cols:
                header_html += f"<th>{sub}</th>"
        header_html += "</tr></thead>"
        data_cols = [f"{t}_{s}" for t in trt_cols for s in sub_cols]
    else:
        # 单行表头
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
            # 跳过 exclude=1 的行
            if int(row.get("exclude") or 0) == 1:
                continue

            cur_class = row.get("Class")
            # Class 变化时插入空行
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
    content = badge + table_html + _footnotes_html(card)
    return f"{_BASE_CSS}<div class='tfl-preview'>{_header_html(card)}{content}</div>"
```

**Step 4: 运行测试确认通过**

```bash
cd web && python -m pytest tests/test_tfl_preview.py -v
```
预期：全部 PASS（含新增 6 个 pstab 测试）

**Step 5: Commit**

```bash
git add web/tfl_preview.py web/tests/test_tfl_preview.py
git commit -m "feat(web): implement PStab HTML preview with three-line table"
```

---

## Task 3：RptList / 图形 / mtext HTML 渲染

**Files:**
- Modify: `web/tfl_preview.py` — 实现 3 个占位函数
- Modify: `web/tests/test_tfl_preview.py` — 添加测试

**Step 1: 写失败测试**

在 `test_tfl_preview.py` 末尾追加：

```python
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
```

**Step 2: 运行测试确认失败**

```bash
cd web && python -m pytest tests/test_tfl_preview.py::test_rptlist_html_contains_table tests/test_tfl_preview.py::test_figure_html_shows_placeholder tests/test_tfl_preview.py::test_mtext_shows_reftfl -v
```
预期：3 FAIL（占位符实现）

**Step 3: 实现 `_render_rptlist`**

替换占位实现：

```python
def _render_rptlist(card: dict, datasets: dict) -> str:
    ds_name = str(card.get("Datasets") or "").strip()
    list_df = datasets.get("list")

    badge = "<div class='tfl-badge'>📋 清单视图（横向A4模拟）</div>"

    if list_df is None or list_df.empty:
        content = badge + "<p style='color:#aaa;font-size:9pt'>（无 list 数据集）</p>"
        return f"{_BASE_CSS}<div class='tfl-preview'>{_header_html(card)}{content}</div>"

    # 筛选对应 ListName 的行，排除 exclude=1
    rows = list_df[
        (list_df.get("ListName", pd.Series(dtype=str)) == ds_name) &
        (list_df.get("exclude", pd.Series(0, index=list_df.index)).fillna(0).astype(int) != 1)
    ] if "ListName" in list_df.columns else list_df

    if rows.empty:
        rows = list_df[list_df.get("exclude", pd.Series(0, index=list_df.index)).fillna(0).astype(int) != 1]

    cols = [str(r) for r in rows.get("Lvalable", pd.Series()).tolist() if str(r).strip()]

    if not cols:
        content = badge + "<p style='color:#aaa;font-size:9pt'>（无列定义）</p>"
        return f"{_BASE_CSS}<div class='tfl-preview'>{_header_html(card)}{content}</div>"

    # 最多显示 10 列
    cols = cols[:10]
    header_row = "".join(f"<th style='background:#eee;font-size:9pt'>{c}</th>" for c in cols)
    # 模拟 3 行空数据占位
    data_row = "".join(f"<td style='font-size:9pt;color:#ccc'>────</td>" for _ in cols)
    rows_html = "".join(f"<tr>{data_row}</tr>" for _ in range(3))

    table_html = (
        f"<table class='tfl-table' style='font-size:9pt'>"
        f"<thead><tr>{header_row}</tr></thead>"
        f"<tbody>{rows_html}</tbody></table>"
    )
    content = badge + table_html + _footnotes_html(card)
    return f"{_BASE_CSS}<div class='tfl-preview'>{_header_html(card)}{content}</div>"
```

**Step 4: 实现 `_render_figure`**

替换占位实现：

```python
_FIGURE_ICONS = {
    "KMplot": "📈", "Swimplot": "🏊", "WaterfallPlot": "📊",
    "Spiderplot": "🕷️", "Seriesplot": "📉", "Forestplot": "🌲",
}

def _render_figure(card: dict) -> str:
    macvar  = str(card.get("MacVar") or "")
    trtlab  = str(card.get("Trtlab") or "").strip()
    icon    = _FIGURE_ICONS.get(macvar, "📊")
    placeholder = (
        f"<div class='tfl-placeholder'>"
        f"{icon}&nbsp;&nbsp;{macvar}（图形将在 R 端渲染）"
        f"</div>"
    )
    if trtlab:
        groups = " / ".join(trtlab.split("|"))
        placeholder += f"<div class='tfl-caption' style='margin-top:4px'>治疗组：{groups}</div>"
    badge = "<div class='tfl-badge'>📊 图形占位</div>"
    content = badge + placeholder + _footnotes_html(card)
    return f"{_BASE_CSS}<div class='tfl-preview'>{_header_html(card)}{content}</div>"
```

**Step 5: 实现 `_render_mtext`**

替换占位实现：

```python
def _render_mtext(card: dict) -> str:
    reftfl = str(card.get("RefTFL") or "").strip()
    if reftfl:
        ref_html = (
            f"<p style='font-size:11pt'>格式同表 "
            f"<span style='color:#1a6091;font-weight:bold'>{reftfl}</span></p>"
            f"<p style='font-size:9pt;color:#888'>（在左侧导航树中找到该表查看结构）</p>"
        )
    else:
        ref_html = "<p style='color:#aaa'>（未设置 RefTFL）</p>"
    badge = "<div class='tfl-badge'>🔗 引用已有表格</div>"
    content = badge + ref_html + _footnotes_html(card)
    return f"{_BASE_CSS}<div class='tfl-preview'>{_header_html(card)}{content}</div>"
```

**Step 6: 运行全部测试**

```bash
cd web && python -m pytest tests/test_tfl_preview.py -v
```
预期：全部 PASS

**Step 7: Commit**

```bash
git add web/tfl_preview.py web/tests/test_tfl_preview.py
git commit -m "feat(web): implement RptList, figure, mtext HTML previews"
```

---

## Task 4：集成到 `config_editor.py`

**Files:**
- Modify: `web/config_editor.py:342`（`_render_level1` 末尾）

**Goal:** 在 `_render_level1` 末尾，将「展开更多」expander 包进「✏️ 编辑」tab，旁边加「👁️ 预览」tab，预览 tab 调用 `tfl_preview.render_preview()` + 「🔄 用R真实渲染」按钮。

**注意：** 此 task 无单元测试（纯 Streamlit UI 逻辑），靠手动验证。

**Step 1: 在 `config_editor.py` 顶部添加 import**

找到文件顶部 import 区域（约第 1-10 行），确认没有 `tfl_preview` import，添加：

```python
# 在文件顶部 import 块末尾添加（放在 from schema import ... 之后）
import tfl_preview as _tfl_preview
```

**Step 2: 修改 `_render_level1` 末尾**

找到 `_render_level1` 中「展开更多」区域（约第 508 行）：

```python
        # 展开更多：footnote + level2 字段
        with st.expander("展开更多 ▼"):
            ...
            _render_level2(card, card_state, version)
```

将这整段替换为 tabs 结构：

```python
        # ── 编辑 / 预览 双 tab ────────────────────────────────────────────
        tab_edit, tab_preview = st.tabs(["✏️ 编辑", "👁️ 预览"])

        with tab_edit:
            with st.expander("展开更多 ▼"):
                fn_snippets: list = templates.get("footnote_snippets", [])
                for fn in ["footnote1", "footnote2", "footnote3", "footnote4",
                           "footnote5", "footnote6", "footnote7"]:
                    if fn_snippets:
                        fn_col, fn_ins_col = st.columns([5, 1])
                        val = str(card.get(fn, "") or "")
                        new_val = fn_col.text_input(fn, value=val, key=f"cfg_{fn}_{card_id}_{version}")
                        if new_val != val:
                            st.session_state[_CARD_STATE_KEY] = _update_card(
                                st.session_state[_CARD_STATE_KEY], card_id, **{fn: new_val}
                            )
                            st.rerun()
                        chosen = fn_ins_col.selectbox(
                            "插入", ["＋"] + fn_snippets,
                            key=f"cfg_{fn}_ins_{card_id}_{version}",
                            label_visibility="collapsed",
                        )
                        if chosen != "＋":
                            cur = str(card.get(fn, "") or "")
                            merged = (cur + "；" + chosen).lstrip("；")
                            st.session_state[_CARD_STATE_KEY] = _update_card(
                                st.session_state[_CARD_STATE_KEY], card_id, **{fn: merged}
                            )
                            st.rerun()
                    else:
                        _field(st, card, fn, card_id, version)
                _render_level2(card, card_state, version)

        with tab_preview:
            _render_card_preview(card, card_id, version)
```

**Step 3: 添加 `_render_card_preview` 函数**

在 `_render_level2` 函数定义之前（约第 539 行）插入：

```python
def _render_card_preview(card: dict, card_id: str, version: int) -> None:
    """预览 tab 内容：快速 HTML 预览 + 真实渲染按钮。"""
    import streamlit as st

    datasets = st.session_state.get("datasets", {})
    card_state = st.session_state.get(_CARD_STATE_KEY, [])
    cur_card = next((c for c in card_state if c["_id"] == card_id), card)

    # 快速 HTML 预览
    html = _tfl_preview.render_preview(cur_card, datasets)
    st.markdown(html, unsafe_allow_html=True)

    st.divider()

    # 真实渲染按钮
    col_btn, col_status = st.columns([1.5, 3])
    with col_btn:
        if st.button("🔄 用R真实渲染", key=f"cfg_real_render_{card_id}_{version}",
                     help="调用R生成单表Word文档，可下载"):
            from renderer import run_preview as _run_preview
            with st.spinner("R 渲染中..."):
                result = _run_preview(cur_card, datasets)
            st.session_state["preview_result"] = result
            st.session_state["preview_card_title"] = str(
                cur_card.get("title") or cur_card.get("table no") or "TFL"
            )
            st.rerun()

    with col_status:
        pr = st.session_state.get("preview_result")
        if pr and pr.get("status") == "success":
            pr_title = st.session_state.get("preview_card_title", "TFL")
            size_kb = len(pr["output_bytes"]) // 1024 if pr.get("output_bytes") else 0
            st.download_button(
                label=f"📥 下载 {pr_title}.docx",
                data=pr["output_bytes"],
                file_name=f"preview_{pr_title}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                key=f"cfg_dl_{card_id}_{version}",
            )
            st.caption(f"文件大小 {size_kb} KB")
```

> **注意：** `config_editor.py` 里已有「展开更多」的 footnote 渲染代码。Task 4 Step 2 是**完整替换**那段代码为 tabs 结构，确保 footnote 渲染代码出现在 `tab_edit` 内，而不是在外面重复。先用 Read 工具读取第 508-536 行再做精确替换。

**Step 4: 手动验证**

```bash
cd web && streamlit run app.py --server.port 8501
```

1. 加载任意 YAML（如 `config_sample.yaml`）
2. 在 Config章节表格视图，点击某行 title 进入卡片视图
3. 确认卡片底部出现「✏️ 编辑」和「👁️ 预览」两个 tab
4. 切换到「👁️ 预览」tab，确认显示 HTML 表格（PStab）或占位图（图形）
5. 点「🔄 用R真实渲染」，确认下方出现下载按钮

**Step 5: 运行全部测试确认没有回归**

```bash
cd web && python -m pytest tests/ -v
```
预期：全部 PASS（42 + 新增测试）

**Step 6: Commit**

```bash
git add web/config_editor.py
git commit -m "feat(web): integrate tfl quick preview tab into card level1 view"
```

---

## 执行顺序

Tasks 1-3 顺序执行（后者依赖前者的模块存在），Task 4 最后执行（依赖前三个 task 的完整实现）。

| Task | 内容 | 文件 | 预估时间 |
|------|------|------|---------|
| 1 | 模块骨架 + CSS | 新建 `tfl_preview.py` | 10 min |
| 2 | PStab 三线表 HTML | `tfl_preview.py` | 20 min |
| 3 | RptList / 图形 / mtext | `tfl_preview.py` | 20 min |
| 4 | 集成到卡片视图 | `config_editor.py` | 20 min |
