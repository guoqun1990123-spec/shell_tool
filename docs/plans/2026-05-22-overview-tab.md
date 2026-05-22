# 项目总览标签页与全局操作 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在 Config 编辑界面增加 4 个顶层标签页（Config章节、Datasets、项目总览、模板配置），并在项目总览页提供章节统计表和快速导航功能。

**Architecture:** 新建 `web/overview.py` 负责总览渲染（纯视图层，接收 card_state + render_status 参数）；在 `web/app.py` 用 `st.tabs` 将现有 Config主表、Datasets子表、模板管理3块内容分别移入对应标签页；工具栏（加载/新建）和底部操作按钮（保存/渲染/提交）保持全局可见，不进标签页。快速导航点击章节后写入 `section_nav_filter.section` 并切换到 `tab_config`（通过 `st.session_state["active_tab"]` 路由）。

**Tech Stack:** Streamlit st.tabs + session_state，Python 标准库

---

### Task 1: 新建 `web/overview.py` — 章节统计 + 快速导航

**Files:**
- Create: `web/overview.py`

**Step 1: 创建 overview.py**

```python
# web/overview.py
"""项目总览页 —— 纯视图层，不修改数据。"""
from __future__ import annotations
import re
import streamlit as st

_ACTIVE_TAB_KEY = "active_tab"          # "config" | "datasets" | "overview" | "templates"
_NAV_FILTER_KEY = "section_nav_filter"  # 复用 section_nav 的筛选 key


def _sec_sort_key(sec_no: str) -> tuple:
    parts = re.split(r"[.\-]", sec_no.strip())
    result = []
    for p in parts:
        try:
            result.append(int(p))
        except ValueError:
            result.append(p)
    return tuple(result)


def compute_section_stats(card_state: list[dict]) -> list[dict]:
    """
    按 Section no 统计表/图/列表数量，返回有序列表：
    [{"section_no": "14.1", "section_title": "...", "表": 3, "图": 0, "列表": 0, "合计": 3}, ...]
    最后追加合计行。
    """
    stats: dict[str, dict] = {}
    for card in card_state:
        sec = str(card.get("Section no") or "").strip()
        cat = str(card.get("cat") or "").strip()
        if not sec:
            sec = "（无章节）"
        if sec not in stats:
            stats[sec] = {
                "section_no": sec,
                "section_title": str(card.get("Section title") or "").strip(),
                "表": 0, "图": 0, "列表": 0,
            }
        if cat in ("表", "图", "列表"):
            stats[sec][cat] += 1
        else:
            stats[sec].setdefault("其他", 0)
            stats[sec]["其他"] = stats[sec].get("其他", 0) + 1

    rows = sorted(
        stats.values(),
        key=lambda r: (1,) if r["section_no"] == "（无章节）" else (0, *_sec_sort_key(r["section_no"])),
    )
    for r in rows:
        r["合计"] = r["表"] + r["图"] + r["列表"] + r.get("其他", 0)

    total = {"section_no": "合计", "section_title": "", "表": 0, "图": 0, "列表": 0, "合计": 0}
    for r in rows:
        for k in ("表", "图", "列表", "合计"):
            total[k] += r[k]
    rows.append(total)
    return rows


def render_overview(
    card_state: list[dict],
    render_status: dict,
    protocol_name: str,
) -> None:
    """渲染项目总览页。"""
    st.subheader("📊 项目总览")

    # ── 基本信息 ──────────────────────────────────────────────────────────────
    total_cards = len(card_state)
    st.caption(f"方案简称：**{protocol_name or '（未填写）'}**　　TFL 总数：**{total_cards}**")

    st.divider()

    # ── 章节统计表 ──────────────────────────────────────────────────────────
    st.markdown("**章节统计**")
    rows = compute_section_stats(card_state)

    if not card_state:
        st.info("暂无 TFL 数据，请先加载或新建配置。")
    else:
        import pandas as pd
        df = pd.DataFrame(rows, columns=["section_no", "section_title", "表", "图", "列表", "合计"])
        df = df.rename(columns={"section_no": "Section", "section_title": "标题"})
        st.dataframe(df, use_container_width=True, hide_index=True)

    st.divider()

    # ── 快速导航 ─────────────────────────────────────────────────────────────
    st.markdown("**快速导航**")
    nav_rows = [r for r in rows if r["section_no"] != "合计" and r["section_no"] != "（无章节）"]
    if nav_rows:
        cols = st.columns(min(len(nav_rows), 4))
        for i, row in enumerate(nav_rows):
            sec = row["section_no"]
            title = row["section_title"]
            count = row["合计"]
            label = f"{sec}"
            if title:
                label += f" {title[:6]}"
            label += f"({count})"
            with cols[i % 4]:
                if st.button(label, key=f"ov_nav_{sec}", use_container_width=True):
                    # 切换到 Config章节标签页并筛选该章节
                    nav_filt = st.session_state.get(_NAV_FILTER_KEY, {})
                    nav_filt["section"] = sec
                    nav_filt["scroll_to"] = None
                    st.session_state[_NAV_FILTER_KEY] = nav_filt
                    st.session_state["section_nav_view_mode"] = "card"
                    st.session_state[_ACTIVE_TAB_KEY] = "config"
                    st.rerun()
    else:
        st.caption("无章节数据")

    st.divider()

    # ── 最近渲染状态 ─────────────────────────────────────────────────────────
    st.markdown("**最近渲染**")
    rs = render_status
    status = rs.get("status", "idle")
    if status == "success":
        elapsed = rs.get("elapsed") or 0
        size_kb = len(rs["output_bytes"]) // 1024 if rs.get("output_bytes") else 0
        st.success(f"✅ 上次渲染成功（耗时 {elapsed:.1f}s，{size_kb} KB）")
        if rs.get("output_bytes"):
            st.download_button(
                label="📥 下载 output.docx",
                data=rs["output_bytes"],
                file_name=rs.get("output_name") or "output.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                key="ov_download",
            )
    elif status == "error":
        elapsed = rs.get("elapsed") or 0
        summary = rs.get("error_summary") or "未知错误"
        st.error(f"❌ 上次渲染失败（耗时 {elapsed:.1f}s）：{summary}")
    else:
        st.caption("尚未渲染")
```

**Step 2: 验证语法**

```bash
cd /d/shell_tool/web && python -c "from overview import compute_section_stats, render_overview; print('OK')"
```

Expected: `OK`

**Step 3: 单元测试 compute_section_stats**

新建 `web/tests/test_overview.py`：

```python
"""overview 纯函数单元测试。"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from overview import compute_section_stats


def test_empty_returns_totals_row_only():
    result = compute_section_stats([])
    assert result == [{"section_no": "合计", "section_title": "",
                       "表": 0, "图": 0, "列表": 0, "合计": 0}]


def test_basic_counts():
    cards = [
        {"Section no": "14.1", "Section title": "人口学", "cat": "表"},
        {"Section no": "14.1", "Section title": "人口学", "cat": "表"},
        {"Section no": "14.2", "Section title": "安全性", "cat": "图"},
    ]
    rows = compute_section_stats(cards)
    # 排除合计行
    data = [r for r in rows if r["section_no"] != "合计"]
    assert data[0]["section_no"] == "14.1"
    assert data[0]["表"] == 2
    assert data[0]["合计"] == 2
    assert data[1]["section_no"] == "14.2"
    assert data[1]["图"] == 1
    assert data[1]["合计"] == 1


def test_totals_row():
    cards = [
        {"Section no": "14.1", "cat": "表"},
        {"Section no": "14.2", "cat": "列表"},
    ]
    rows = compute_section_stats(cards)
    totals = rows[-1]
    assert totals["section_no"] == "合计"
    assert totals["表"] == 1
    assert totals["列表"] == 1
    assert totals["合计"] == 2


def test_section_sorted_numerically():
    cards = [
        {"Section no": "14.10", "cat": "表"},
        {"Section no": "14.2", "cat": "表"},
        {"Section no": "14.1", "cat": "表"},
    ]
    rows = compute_section_stats(cards)
    data = [r["section_no"] for r in rows if r["section_no"] != "合计"]
    assert data == ["14.1", "14.2", "14.10"]


def test_no_section_sorts_last():
    cards = [
        {"Section no": "", "cat": "表"},
        {"Section no": "14.1", "cat": "表"},
    ]
    rows = compute_section_stats(cards)
    data = [r["section_no"] for r in rows if r["section_no"] != "合计"]
    assert data[0] == "14.1"
    assert data[-1] == "（无章节）"
```

**Step 4: 运行测试**

```bash
cd /d/shell_tool/web && python -m pytest tests/test_overview.py -v
```

Expected: 5 tests PASS

**Step 5: Commit**

```bash
git add web/overview.py web/tests/test_overview.py
git commit -m "feat(web): add overview.py with section stats and navigation"
```

---

### Task 2: app.py — 重构为 4 标签页布局

**Files:**
- Modify: `web/app.py`

**背景：**
当前 `main()` 函数是线性结构：工具栏 → Config主表 → Datasets子表 → 模板管理 → 操作按钮 → 渲染结果。
目标：在工具栏和操作按钮之间插入 `st.tabs`，将中间内容分入4个标签页。

**Step 1: 在 app.py 顶部 import 区域添加 overview 导入**

找到：
```python
from section_table import render_section_table
```

在其后追加：
```python
from overview import render_overview, _ACTIVE_TAB_KEY
```

**Step 2: 在 `_init_state` 中添加 active_tab 初始化**

找到 `_init_state` 函数末尾（最后一个 `if "render_status" not in` 块之后），追加：
```python
    if "active_tab" not in st.session_state:
        st.session_state["active_tab"] = "config"
```

**Step 3: 替换 main() 中间区域（Config主表 → 模板管理）为 st.tabs**

找到（约 L182）：
```python
    # ── Config 主表（左右分栏）──────────────────────────────────────────────
    st.subheader("Config 主表")
```

一直到（约 L451）：
```python
    # ── 状态栏 + 保存按钮 ───────────────────────────────────────────────────
    st.divider()
```

将这整段替换为：

```python
    # ── 标签页 ──────────────────────────────────────────────────────────────
    _active = st.session_state.get(_ACTIVE_TAB_KEY, "config")
    _tab_names = ["📋 Config章节", "🗂 Datasets", "📊 项目总览", "⚙️ 模板配置"]
    _tab_keys  = ["config",        "datasets",   "overview",   "templates"]
    _tab_index = _tab_keys.index(_active) if _active in _tab_keys else 0

    tab_config, tab_datasets, tab_overview, tab_templates = st.tabs(_tab_names)

    # ── Tab: Config章节 ──────────────────────────────────────────────────────
    with tab_config:
        _nav_col, _edit_col = st.columns([1, 3], gap="small")

        with _nav_col:
            _current_card_state = st.session_state.get(_CFG_CARD_KEY, [])
            render_section_nav(_current_card_state)

        with _edit_col:
            dataset_keys = list(st.session_state.datasets.keys())
            cfg_templates = load_config_templates()

            _view_mode = st.session_state.get("section_nav_view_mode", "card")
            _table_sec = st.session_state.get("section_nav_table_section", "")

            if _view_mode == "table" and _table_sec:
                render_section_table(
                    st.session_state.get(_CFG_CARD_KEY, []),
                    _table_sec,
                    dataset_keys,
                    cfg_templates,
                )
                from config_editor import card_state_to_df
                edited_config = card_state_to_df(st.session_state.get(_CFG_CARD_KEY, []))
                selected_idx = st.session_state.selected_row
            else:
                edited_config, selected_idx = render_config_editor(
                    st.session_state.config_df,
                    dataset_keys,
                    cfg_templates,
                )
                st.session_state.selected_row = selected_idx

    # ── Tab: Datasets ────────────────────────────────────────────────────────
    with tab_datasets:
        # edited_config / selected_idx 必须来自 Config 标签页的计算结果
        # 当处于 Datasets 标签时 Config 标签未渲染，需从 session_state 读取
        _cs = st.session_state.get(_CFG_CARD_KEY, [])
        from config_editor import card_state_to_df as _cs2df
        edited_config_ds = _cs2df(_cs)
        sel_idx_ds = st.session_state.get("selected_row")

        if sel_idx_ds is not None and sel_idx_ds < len(edited_config_ds):
            sel_row = edited_config_ds.iloc[sel_idx_ds]
            ds_name = str(sel_row.get("Datasets", "") or "").strip()
            macvar = str(sel_row.get("MacVar", "") or "").strip()
            seq_no = sel_row.get("SeqNum", "?")
            st.caption(f"当前选中：SeqNum={seq_no}，Datasets='{ds_name}'，MacVar='{macvar}'")
        else:
            ds_name = ""
            st.info("请先在「Config章节」标签页中点击某行以选中，再切换此标签查看数据表。")

        col_dsname, col_dsadd = st.columns([3, 1])
        with col_dsname:
            new_ds_name = st.text_input("新建数据表名", placeholder="如 t_demo", key="new_ds_name")
        with col_dsadd:
            st.write("")
            if st.button("新建数据表", key="btn_add_ds"):
                if new_ds_name and new_ds_name not in st.session_state.datasets:
                    is_list = new_ds_name == "list"
                    st.session_state.datasets[new_ds_name] = (
                        _empty_dataset_list() if is_list else _empty_dataset_table()
                    )
                    st.rerun()

        if ds_name and ds_name in st.session_state.datasets:
            is_list = ds_name == "list"
            ds_df = st.session_state.datasets[ds_name]

            if is_list:
                ds_cc = _build_list_column_config()
                edited_ds = st.data_editor(
                    ds_df,
                    column_config=ds_cc,
                    num_rows="dynamic",
                    width="stretch",
                    key=f"ds_editor_{ds_name}_{st.session_state.editor_version}",
                )
                st.session_state.datasets[ds_name] = edited_ds
            else:
                card_key = state_key(ds_name)
                version_key = f"_ds_version_{ds_name}"
                if st.session_state.get(version_key) != st.session_state.editor_version:
                    st.session_state[card_key] = df_to_card_state(ds_df)
                    st.session_state[version_key] = st.session_state.editor_version

                tab_edit, tab_preview = st.tabs(["✏️ 编辑", "👁️ 结构预览"])
                with tab_edit:
                    templates = load_templates()
                    result_df = render_dataset_editor(ds_name, ds_df, templates)
                    st.session_state.datasets[ds_name] = result_df
                with tab_preview:
                    render_preview(ds_name, st.session_state.get(card_key, []))

        elif ds_name:
            st.info(f"数据表 '{ds_name}' 尚未创建，请在上方新建。")

    # ── Tab: 项目总览 ────────────────────────────────────────────────────────
    with tab_overview:
        render_overview(
            card_state=st.session_state.get(_CFG_CARD_KEY, []),
            render_status=st.session_state.render_status,
            protocol_name=st.session_state.protocol_name,
        )

    # ── Tab: 模板配置 ────────────────────────────────────────────────────────
    with tab_templates:
        cfg_tmpl_ver = st.session_state.get("cfg_tmpl_version", 0)

        with st.expander("变量类型模板配置", expanded=True):
            from templates_io import save_templates
            templates_edit = load_templates()

            st.caption("连续变量子行（Label + Aval 模板）")
            cont_tmpl = templates_edit.get("连续变量", {})
            cont_children = cont_tmpl.get("children", [])
            new_children = []
            for j, child in enumerate(cont_children):
                c1, c2, c3 = st.columns([3, 3, 0.5])
                with c1:
                    lbl = st.text_input(
                        "Label", value=child.get("Label", ""),
                        label_visibility="collapsed",
                        key=f"tmpl_label_{st.session_state.tmpl_version}_{j}"
                    )
                with c2:
                    avl = st.text_input(
                        "Aval", value=child.get("Aval", ""),
                        label_visibility="collapsed",
                        key=f"tmpl_aval_{st.session_state.tmpl_version}_{j}"
                    )
                with c3:
                    if not st.button("🗑", key=f"tmpl_del_{st.session_state.tmpl_version}_{j}"):
                        new_children.append({"Label": lbl, "Aval": avl})
            if st.button("＋ 添加子行", key="tmpl_add"):
                new_children.append({"Label": "", "Aval": ""})
            templates_edit.setdefault("连续变量", {})["children"] = new_children

            col_a, col_b = st.columns(2)
            with col_a:
                st.caption("分类变量-无子分类 Aval")
                templates_edit.setdefault("分类变量-无子分类", {})["aval"] = st.text_input(
                    "Aval",
                    value=templates_edit.get("分类变量-无子分类", {}).get("aval", "xx (xx.x)"),
                    key="tmpl_cat_aval",
                    label_visibility="collapsed",
                )
            with col_b:
                st.caption("日期变量 Aval")
                templates_edit.setdefault("日期变量", {})["aval"] = st.text_input(
                    "Aval",
                    value=templates_edit.get("日期变量", {}).get("aval", "YYYY-MM-DD"),
                    key="tmpl_date_aval",
                    label_visibility="collapsed",
                )
            if st.button("保存模板", key="btn_save_tmpl", type="secondary"):
                try:
                    save_templates(templates_edit)
                    st.cache_data.clear()
                    st.session_state.tmpl_version += 1
                    st.success("模板已保存")
                except OSError as e:
                    st.error(f"保存失败：{e}")

        with st.expander("⚙️ Config 模板配置", expanded=True):
            tab_sec, tab_pop, tab_levels = st.tabs(["Section 映射", "pop 选项", "显示级别"])

            with tab_sec:
                cfg_tmpl_edit = load_config_templates()
                sec_map: dict = dict(cfg_tmpl_edit.get("section_map", {}))
                sec_items = list(sec_map.items())
                new_sec_map: dict = {}
                for j, (k, v) in enumerate(sec_items):
                    sc1, sc2, sc3 = st.columns([2, 3, 0.5])
                    with sc1:
                        new_k = st.text_input(
                            "Section no", value=k, label_visibility="collapsed",
                            key=f"cfgtmpl_secno_{cfg_tmpl_ver}_{j}",
                        )
                    with sc2:
                        new_v = st.text_input(
                            "Section title", value=v, label_visibility="collapsed",
                            key=f"cfgtmpl_sectitle_{cfg_tmpl_ver}_{j}",
                        )
                    with sc3:
                        if not st.button("🗑", key=f"cfgtmpl_secdel_{cfg_tmpl_ver}_{j}"):
                            if new_k.strip():
                                new_sec_map[new_k.strip()] = new_v
                if st.button("＋ 添加 Section", key="cfgtmpl_secadd"):
                    new_sec_map[""] = ""
                cfg_tmpl_edit["section_map"] = new_sec_map
                if st.button("保存 Section 映射", key="btn_save_secmap", type="secondary"):
                    try:
                        save_config_templates(cfg_tmpl_edit)
                        st.cache_data.clear()
                        st.session_state["cfg_tmpl_version"] = cfg_tmpl_ver + 1
                        st.success("已保存")
                    except OSError as e:
                        st.error(f"保存失败：{e}")

            with tab_pop:
                cfg_tmpl_pop = load_config_templates()
                pop_opts: list = list(cfg_tmpl_pop.get("pop_options", []))
                new_pop_opts: list = []
                for j, opt in enumerate(pop_opts):
                    pc1, pc2 = st.columns([4, 0.5])
                    with pc1:
                        new_opt = st.text_input(
                            "pop", value=opt, label_visibility="collapsed",
                            key=f"cfgtmpl_pop_{cfg_tmpl_ver}_{j}",
                        )
                    with pc2:
                        if not st.button("🗑", key=f"cfgtmpl_popdel_{cfg_tmpl_ver}_{j}"):
                            if new_opt.strip():
                                new_pop_opts.append(new_opt.strip())
                if st.button("＋ 添加人群", key="cfgtmpl_popadd"):
                    new_pop_opts.append("")
                cfg_tmpl_pop["pop_options"] = new_pop_opts
                if st.button("保存 pop 选项", key="btn_save_pop", type="secondary"):
                    try:
                        save_config_templates(cfg_tmpl_pop)
                        st.cache_data.clear()
                        st.session_state["cfg_tmpl_version"] = cfg_tmpl_ver + 1
                        st.success("已保存")
                    except OSError as e:
                        st.error(f"保存失败：{e}")

            with tab_levels:
                from schema import CONFIG_COLS as _ALL_COLS
                disp_cfg = load_display_levels()
                field_levels: dict = disp_cfg.get("field_levels", {})
                level_options = ["一级", "二级", "不显示"]
                level_map = {"level1": "一级", "level2": "二级", "hidden": "不显示"}
                level_rev = {"一级": "level1", "二级": "level2", "不显示": "hidden"}
                new_field_levels: dict = {}
                st.caption("字段  →  显示级别（必显示字段锁定不可修改）")
                for field in _ALL_COLS:
                    cur_level = field_levels.get(field, "level2")
                    if field in REQUIRED_FIELDS:
                        st.text(f"  {field:<28} 必显示 🔒")
                        new_field_levels[field] = "required"
                    else:
                        cur_label = level_map.get(cur_level, "二级")
                        lc1, lc2 = st.columns([3, 1.5])
                        with lc1:
                            st.caption(field)
                        with lc2:
                            new_label = st.selectbox(
                                field, options=level_options,
                                index=level_options.index(cur_label),
                                key=f"disp_level_{cfg_tmpl_ver}_{field}",
                                label_visibility="collapsed",
                            )
                        new_field_levels[field] = level_rev[new_label]
                if st.button("保存显示设置", key="btn_save_disp", type="secondary"):
                    try:
                        save_display_levels({
                            "default_collapse": disp_cfg.get("default_collapse", True),
                            "field_levels": new_field_levels,
                        })
                        st.cache_data.clear()
                        st.session_state["cfg_tmpl_version"] = cfg_tmpl_ver + 1
                        st.success("显示设置已保存")
                    except OSError as e:
                        st.error(f"保存失败：{e}")

    # ── 校验（需要 edited_config，从 Config 标签获取） ─────────────────────────
    # edited_config 在 tab_config 内定义；当处于其他标签时需 fallback
    try:
        _ = edited_config
    except NameError:
        from config_editor import card_state_to_df as _cs2df2
        edited_config = _cs2df2(st.session_state.get(_CFG_CARD_KEY, []))

    errors = validate(edited_config, st.session_state.datasets)

    # ── 状态栏 + 保存按钮 ───────────────────────────────────────────────────
    st.divider()
```

**Step 4: 同步修正 `_do_save` 引用**

在 `_do_save` 函数中，找到：
```python
    content = dump_yaml(
        st.session_state.config_df,
```

确认 `st.session_state.config_df` 仍然是正确的来源（它在加载时更新，所以没问题）。不需要修改。

**Step 5: 验证语法**

```bash
cd /d/shell_tool/web && python -c "import app; print('OK')"
```

Expected: `OK`

**Step 6: Commit**

```bash
git add web/app.py
git commit -m "feat(web): reorganize app into 4-tab layout with Config/Datasets/Overview/Templates"
```

---

### Task 3: 验收测试

**Step 1: 运行所有测试**

```bash
cd /d/shell_tool/web && python -m pytest tests/ -v
```

Expected: 所有测试 PASS（包含 test_overview.py 5条）

**Step 2: 启动 Web**

```bash
cd /d/shell_tool && streamlit run web/app.py --server.port 8501
```

**Step 3: 逐项验收**

- [ ] 页面正常加载，顶部显示 4 个标签：📋 Config章节 / 🗂 Datasets / 📊 项目总览 / ⚙️ 模板配置
- [ ] 工具栏（方案简称、加载、新建）在标签页上方全局可见
- [ ] 底部操作按钮（💾 保存草稿 / 🚀 生成 / 🔒 提交 Git）在标签页下方全局可见
- [ ] Config章节标签：左侧导航树 + 右侧卡片/表格视图正常
- [ ] Datasets标签：先在Config章节选中行，再切换到Datasets，显示对应数据表
- [ ] 项目总览标签：显示章节统计表，行数与实际 TFL 数量匹配
- [ ] 项目总览快速导航：点击章节按钮 → 切换到 Config章节标签并筛选
- [ ] 项目总览渲染状态：初始显示「尚未渲染」；渲染成功后显示「✅」和下载按钮
- [ ] 模板配置标签：原有「变量类型模板」和「Config模板配置」功能正常
- [ ] 校验错误时底部显示错误，保存按钮 disabled
- [ ] 保存草稿、生成TFL Shell、提交Git 流程不受影响

**Step 4: 最终 Commit（如有遗留修复）**

```bash
git add web/
git commit -m "fix(web): overview tab polish"
```
