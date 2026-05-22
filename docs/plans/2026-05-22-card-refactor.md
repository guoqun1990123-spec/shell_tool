# 单条卡片重构实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 重构单条 TFL 卡片编辑界面，将8个平铺按钮合并为3组，嵌入 Datasets 迷你面板，并支持从表格视图跳转到单条卡片。

**Architecture:** 主要改动 `web/config_editor.py` 的 `_render_header`（按钮分组）和 `_render_level1`（Datasets面板+展开更多expander）；`web/section_table.py` 的 title 列改跳转按钮；`_level` 状态从4级简化为3级（collapsed/level1/focus），level2 挪入 expander。

**Tech Stack:** Streamlit session_state，Python 标准库

---

### Task 1: config_editor.py — 重构 `_render_header`

**Files:**
- Modify: `web/config_editor.py`

**背景：**  
当前头部有 13 列 8 个按钮（展开/更多/▲/▼/+/复制/删除/🔍），视觉松散。  
目标：6列布局，⋮点击后行内显示复制/删除行。

**Step 1: 添加常量和辅助函数**

在 `config_editor.py` 顶部常量区（`_FILTER_KEY` 之后）追加：

```python
_MENU_OPEN_KEY = "cfg_menu_open"    # set[card_id]，⋮ 菜单展开状态
_DS_OPEN_KEY = "cfg_ds_panel_open"  # set[card_id]，Datasets 面板展开状态


def _menu_open() -> set:
    if _MENU_OPEN_KEY not in st.session_state:
        st.session_state[_MENU_OPEN_KEY] = set()
    return st.session_state[_MENU_OPEN_KEY]


def _ds_open() -> set:
    if _DS_OPEN_KEY not in st.session_state:
        st.session_state[_DS_OPEN_KEY] = set()
    return st.session_state[_DS_OPEN_KEY]
```

**Step 2: 用新版 `_render_header` 完整替换旧版**

将 `_render_header` 函数（L190-L314）整体替换为：

```python
def _render_header(
    card: dict,
    idx: int,
    total: int,
    card_state: list[dict],
    version: int,
) -> None:
    card_id = card["_id"]
    level = card.get("_level", "collapsed")
    is_collapsed = level == "collapsed"
    is_focus = level == "focus"

    seq = idx + 1
    sec = str(card.get("Section no", "") or "")
    cat = str(card.get("cat", "") or "")
    tableno = str(card.get("table no", "") or "")
    title = str(card.get("title", "") or "")
    tbl_overridden = bool(card.get("_tableno_overridden"))
    menu = _menu_open()
    is_menu_open = card_id in menu

    # 摘要信息字符串（展开状态时显示在 c_info）
    info_parts = [f"**{seq}**"]
    if sec:
        info_parts.append(sec)
    if cat:
        info_parts.append(cat)
    tbl_display = (tableno + " ⚠️") if tbl_overridden else tableno
    if tbl_display:
        info_parts.append(tbl_display)
    info_str = " · ".join(info_parts)

    # 6 列布局：收起 | 专注 | ▲ | ▼ | + | ⋮ | 信息/标题
    c_collapse, c_focus, c_up, c_dn, c_ins, c_more, c_info = st.columns(
        [0.55, 0.45, 0.28, 0.28, 0.28, 0.28, 4.5]
    )

    # 收起按钮（仅展开时显示）
    with c_collapse:
        if not is_collapsed:
            if st.button("收起▲", key=f"cfg_collapse_{card_id}_{version}"):
                menu.discard(card_id)
                st.session_state[_MENU_OPEN_KEY] = menu
                st.session_state[_CARD_STATE_KEY] = _update_card(
                    card_state, card_id, _level="collapsed"
                )
                st.rerun()

    # 专注 / 退出专注
    with c_focus:
        if is_focus:
            if st.button("退出🔍", key=f"cfg_unfocus_{card_id}_{version}"):
                st.session_state[_FOCUS_KEY] = None
                st.session_state[_CARD_STATE_KEY] = _update_card(
                    card_state, card_id, _level="level1"
                )
                st.rerun()
        else:
            if st.button("🔍", key=f"cfg_focus_{card_id}_{version}"):
                st.session_state[_FOCUS_KEY] = card_id
                st.session_state[_SELECTED_ID_KEY] = card_id
                st.session_state[_CARD_STATE_KEY] = _update_card(
                    card_state, card_id, _level="focus"
                )
                st.rerun()

    with c_up:
        if st.button("▲", key=f"cfg_up_{card_id}_{version}", disabled=(idx == 0)):
            st.session_state[_CARD_STATE_KEY] = _move_card(card_state, idx, -1)
            st.rerun()

    with c_dn:
        if st.button("▼", key=f"cfg_dn_{card_id}_{version}", disabled=(idx == total - 1)):
            st.session_state[_CARD_STATE_KEY] = _move_card(card_state, idx, +1)
            st.rerun()

    with c_ins:
        if st.button("+", key=f"cfg_ins_{card_id}_{version}"):
            st.session_state[_CARD_STATE_KEY] = _insert_after(card_state, card_id)
            st.rerun()

    # ⋮ 菜单开关
    with c_more:
        if st.button("⋮", key=f"cfg_more_{card_id}_{version}"):
            if is_menu_open:
                menu.discard(card_id)
            else:
                menu.add(card_id)
            st.session_state[_MENU_OPEN_KEY] = menu
            st.rerun()

    # 信息区 / 标题展开入口
    with c_info:
        if is_collapsed:
            btn_label = f"▶ {title[:45]}" if title else "▶ （点击展开）"
            if st.button(btn_label, key=f"cfg_sel_{card_id}_{version}",
                         use_container_width=True):
                st.session_state[_SELECTED_ID_KEY] = card_id
                st.session_state[_CARD_STATE_KEY] = _update_card(
                    card_state, card_id, _level="level1"
                )
                st.rerun()
        else:
            title_short = (title[:50] + "…") if len(title) > 50 else title
            st.caption(f"{info_str} · {title_short}")

    # ⋮ 菜单展开行（复制 / 删除）
    if is_menu_open:
        m1, m2, _ = st.columns([0.8, 0.9, 5.0])
        with m1:
            if st.button("复制", key=f"cfg_copy_{card_id}_{version}"):
                menu.discard(card_id)
                st.session_state[_MENU_OPEN_KEY] = menu
                st.session_state[_CARD_STATE_KEY] = _copy_card(card_state, card_id)
                st.rerun()
        with m2:
            if st.button("🗑 删除", key=f"cfg_del_{card_id}_{version}"):
                menu.discard(card_id)
                st.session_state[_MENU_OPEN_KEY] = menu
                if st.session_state.get(_SELECTED_ID_KEY) == card_id:
                    st.session_state[_SELECTED_ID_KEY] = None
                if st.session_state.get(_FOCUS_KEY) == card_id:
                    st.session_state[_FOCUS_KEY] = None
                st.session_state[_CARD_STATE_KEY] = _delete_card(card_state, card_id)
                st.rerun()
```

**Step 3: 验证语法**

```bash
cd /d/shell_tool/web && python -c "import config_editor; print('OK')"
```

Expected: `OK`

**Step 4: Commit**

```bash
git add web/config_editor.py
git commit -m "refactor(web): restructure card header into 3 button groups with inline menu"
```

---

### Task 2: config_editor.py — `_render_level1` 加 Datasets 面板 + 展开更多

**Files:**
- Modify: `web/config_editor.py`

**背景：**  
当前 level1 最底部是 `st.expander("脚注")` 只放 footnote。  
目标：在 Trtlab 行后加 Datasets 迷你面板，将 footnote + level2 字段统一放入「展开更多」expander。

**Step 1: 用新版 `_render_level1` 完整替换旧版**

将 `_render_level1`（L320-L464）整体替换为：

```python
def _render_level1(
    card: dict,
    card_state: list[dict],
    dataset_keys: list[str],
    templates: dict,
    version: int,
) -> None:
    card_id = card["_id"]
    section_map: dict = templates.get("section_map", {})
    pop_options: list = templates.get("pop_options", [])
    sec = str(card.get("Section no", "") or "")
    cat = str(card.get("cat", "") or "")
    tableno = str(card.get("table no", "") or "")
    tbl_overridden = bool(card.get("_tableno_overridden"))
    title_overridden = bool(card.get("_title_overridden"))
    sec_title_val = str(card.get("Section title", "") or "")
    cur_ds = str(card.get("Datasets", "") or "")

    with st.container():
        # 行A: Section no / Section title / cat / table no
        rA1, rA2, rA3, rA4 = st.columns([1.2, 2.5, 1.0, 1.5])

        with rA1:
            sec_opts = [""] + list(section_map.keys())
            new_sec = st.selectbox(
                "Section no", options=sec_opts,
                index=sec_opts.index(sec) if sec in sec_opts else 0,
                key=f"cfg_secno_{card_id}_{version}",
            )
            if new_sec != sec:
                updates: dict = {"Section no": new_sec}
                if not title_overridden and new_sec in section_map:
                    updates["Section title"] = section_map[new_sec]
                st.session_state[_CARD_STATE_KEY] = _update_card(card_state, card_id, **updates)
                st.rerun()

        with rA2:
            lbl_st = "Section title" + (" ✏️" if title_overridden else "")
            new_sec_title = st.text_input(
                lbl_st, value=sec_title_val,
                key=f"cfg_sectitle_{card_id}_{version}",
            )
            if new_sec_title != sec_title_val:
                st.session_state[_CARD_STATE_KEY] = _update_card(
                    card_state, card_id,
                    **{"Section title": new_sec_title,
                       "_title_overridden": bool(new_sec_title.strip())},
                )
                st.rerun()
            if title_overridden and sec in section_map:
                auto_title = section_map[sec]
                if sec_title_val != auto_title:
                    if st.button(f"↩ 重置为「{auto_title}」",
                                 key=f"cfg_reset_title_{card_id}_{version}"):
                        st.session_state[_CARD_STATE_KEY] = _update_card(
                            card_state, card_id,
                            **{"Section title": auto_title, "_title_overridden": False},
                        )
                        st.rerun()

        with rA3:
            new_cat = st.selectbox(
                "cat", options=CAT_OPTIONS,
                index=CAT_OPTIONS.index(cat) if cat in CAT_OPTIONS else 0,
                key=f"cfg_cat_{card_id}_{version}",
            )
            if new_cat != cat:
                st.session_state[_CARD_STATE_KEY] = _update_card(card_state, card_id, cat=new_cat)
                st.rerun()

        with rA4:
            tbl_lbl = "table no" + (" ⚠️手动" if tbl_overridden else "")
            new_tbl = st.text_input(
                tbl_lbl, value=tableno,
                key=f"cfg_tbl_{card_id}_{version}",
            )
            if new_tbl != tableno:
                st.session_state[_CARD_STATE_KEY] = _update_card(
                    card_state, card_id,
                    **{"table no": new_tbl, "_tableno_overridden": bool(new_tbl.strip())},
                )
                st.rerun()
            if tbl_overridden:
                if st.button("↩ 重置自动编号", key=f"cfg_reset_tbl_{card_id}_{version}"):
                    new_state = _update_card(card_state, card_id, _tableno_overridden=False)
                    st.session_state[_CARD_STATE_KEY] = _compute_table_nos(new_state)
                    st.rerun()

        # 行B: title（全宽）
        _field(st, card, "title", card_id, version)

        # 行C: pop / MacVar / Datasets
        rC1, rC2, rC3 = st.columns([2.5, 1.5, 1.5])

        with rC1:
            cur_pop = str(card.get("pop", "") or "")
            cur_pop_list = [p.strip() for p in cur_pop.split(",") if p.strip()]
            all_pop = list(dict.fromkeys(pop_options + cur_pop_list))
            new_pop_list = st.multiselect(
                "pop", options=all_pop,
                default=[p for p in cur_pop_list if p in all_pop],
                key=f"cfg_pop_{card_id}_{version}",
            )
            new_pop = ", ".join(new_pop_list)
            if new_pop != cur_pop:
                st.session_state[_CARD_STATE_KEY] = _update_card(
                    card_state, card_id, pop=new_pop
                )
                st.rerun()

        with rC2:
            cur_macvar = str(card.get("MacVar", "") or "")
            new_macvar = st.selectbox(
                "MacVar", options=VALID_MACVAR,
                index=VALID_MACVAR.index(cur_macvar) if cur_macvar in VALID_MACVAR else 0,
                key=f"cfg_macvar_{card_id}_{version}",
            )
            if new_macvar != cur_macvar:
                st.session_state[_CARD_STATE_KEY] = _update_card(
                    card_state, card_id, MacVar=new_macvar
                )
                st.rerun()

        with rC3:
            ds_opts = [""] + dataset_keys
            new_ds = st.selectbox(
                "Datasets", options=ds_opts,
                index=ds_opts.index(cur_ds) if cur_ds in ds_opts else 0,
                key=f"cfg_ds_{card_id}_{version}",
            )
            if new_ds != cur_ds:
                st.session_state[_CARD_STATE_KEY] = _update_card(
                    card_state, card_id, Datasets=new_ds
                )
                st.rerun()

        # 行D: Trtlab
        _field(st, card, "Trtlab", card_id, version)

        # Datasets 迷你面板
        ds_open_set = _ds_open()
        is_ds_open = card_id in ds_open_set
        ds_btn_label = (
            f"📎 {cur_ds}  {'收起▲' if is_ds_open else '展开▼'}"
            if cur_ds else "📎 未关联 Datasets"
        )
        if st.button(ds_btn_label, key=f"cfg_ds_toggle_{card_id}_{version}"):
            if is_ds_open:
                ds_open_set.discard(card_id)
            else:
                ds_open_set.add(card_id)
            st.session_state[_DS_OPEN_KEY] = ds_open_set
            st.rerun()

        if is_ds_open:
            datasets = st.session_state.get("datasets", {})
            if cur_ds and cur_ds in datasets:
                ds_df = datasets[cur_ds]
                st.dataframe(ds_df.head(20), height=150, use_container_width=True)
                if st.button("编辑完整 Datasets ▶", key=f"cfg_ds_edit_{card_id}_{version}"):
                    st.session_state[_SELECTED_ID_KEY] = card_id
                    st.toast("已关联到下方 Datasets 编辑器 ↓")
                    st.rerun()
            else:
                st.caption("未关联 Datasets 或数据表尚未创建")

        # 展开更多：footnote + level2 字段
        with st.expander("展开更多 ▼"):
            for fn in ["footnote1", "footnote2", "footnote3", "footnote4",
                       "footnote5", "footnote6", "footnote7"]:
                _field(st, card, fn, card_id, version)
            _render_level2(card, card_state, version)
```

**Step 2: 验证语法**

```bash
cd /d/shell_tool/web && python -c "import config_editor; print('OK')"
```

Expected: `OK`

**Step 3: Commit**

```bash
git add web/config_editor.py
git commit -m "refactor(web): add datasets mini panel and merge level2 into expander in level1"
```

---

### Task 3: config_editor.py — 简化 `_render_card` + focus 横幅加返回按钮

**Files:**
- Modify: `web/config_editor.py`

**背景：**  
`_render_card` 当前对 level2 单独调用 `_render_level2`，现在 level2 已移入 expander，需要清理。  
focus 横幅需要加「← 返回表格视图」按钮。

**Step 1: 替换 `_render_card` 函数**

将 `_render_card`（L489-L522）整体替换为：

```python
def _render_card(
    card: dict,
    idx: int,
    total: int,
    card_state: list[dict],
    dataset_keys: list[str],
    templates: dict,
    version: int,
    focus_id: str | None,
) -> None:
    card_id = card["_id"]
    level = card.get("_level", "collapsed")
    # 兼容旧数据：level2 视为 level1（level2 字段已移入 expander）
    if level == "level2":
        level = "level1"

    # 专注模式下其他卡片只显示占位
    if focus_id and focus_id != card_id:
        sec = str(card.get("Section no", "") or "—")
        title = str(card.get("title", "") or "")
        st.caption(f"··· {idx + 1}. {sec} {title[:30]}")
        return

    _render_header(card, idx, total, card_state, version)

    if level == "collapsed":
        st.divider()
        return

    _render_level1(card, card_state, dataset_keys, templates, version)
    st.divider()
```

**Step 2: 在 `render_config_editor` 中更新 focus 横幅**

找到（约 L610-L612）：
```python
    if focus_id:
        st.info(f"🔍 专注模式中  —  点击卡片上的「退出🔍」按钮退出")
```

替换为：
```python
    if focus_id:
        col_info, col_back = st.columns([4, 1])
        with col_info:
            st.info("🔍 专注模式中 — 点击卡片上的「退出🔍」按钮退出")
        with col_back:
            if st.button("← 返回表格", key="cfg_back_to_table"):
                st.session_state["section_nav_view_mode"] = "table"
                st.session_state[_FOCUS_KEY] = None
                st.rerun()
```

**Step 3: 验证语法**

```bash
cd /d/shell_tool/web && python -c "import config_editor; print('OK')"
```

Expected: `OK`

**Step 4: Commit**

```bash
git add web/config_editor.py
git commit -m "refactor(web): simplify render_card level logic and add back-to-table button in focus banner"
```

---

### Task 4: section_table.py — title 列改为跳转按钮

**Files:**
- Modify: `web/section_table.py`

**背景：**  
目前 title 列是 `st.text_input`，直接编辑。  
目标：改为跳转按钮，点击后切换到卡片视图并聚焦到该卡片；同时导入 `_FOCUS_KEY`。

**Step 1: 在 import 中加入 `_FOCUS_KEY`**

找到：
```python
from config_editor import (
    _CARD_STATE_KEY,
    _update_card,
    _compute_table_nos,
    _delete_card,
    _render_level1,
    _empty_card,
    _insert_after,
    _add_card,
    CAT_OPTIONS,
)
```

替换为：
```python
from config_editor import (
    _CARD_STATE_KEY,
    _FOCUS_KEY,
    _update_card,
    _compute_table_nos,
    _delete_card,
    _render_level1,
    _empty_card,
    _insert_after,
    _add_card,
    CAT_OPTIONS,
)
```

**Step 2: 替换 `_render_row` 中 c3（title）列的内容**

找到（`_render_row` 中 `with c3:` 块）：
```python
    with c3:
        cur_title = str(card.get("title") or "")
        new_title = st.text_input("title", value=cur_title,
                                  key=f"tbl_title_{card_id}_{ver}",
                                  label_visibility="collapsed")
        if new_title != cur_title:
            state = st.session_state[_CARD_STATE_KEY]
            st.session_state[_CARD_STATE_KEY] = _update_card(state, card_id, title=new_title)
            st.rerun()
```

替换为：
```python
    with c3:
        cur_title = str(card.get("title") or "")
        btn_label = cur_title[:35] if cur_title else "（点击进入编辑）"
        if st.button(btn_label, key=f"tbl_goto_{card_id}_{ver}", use_container_width=True):
            st.session_state["section_nav_view_mode"] = "card"
            st.session_state[_FOCUS_KEY] = card_id
            st.session_state[_CARD_STATE_KEY] = _update_card(
                st.session_state[_CARD_STATE_KEY], card_id, _level="level1"
            )
            st.rerun()
```

**Step 3: 验证语法**

```bash
cd /d/shell_tool/web && python -c "import section_table; print('OK')"
```

Expected: `OK`

**Step 4: Commit**

```bash
git add web/section_table.py
git commit -m "feat(web): make title column in section table a jump-to-card button"
```

---

### Task 5: 纯函数单元测试

**Files:**
- Modify: `web/tests/test_dataset_editor.py` → 新建 `web/tests/test_config_editor.py`

**Step 1: 新建测试文件**

创建 `web/tests/test_config_editor.py`：

```python
"""config_editor 纯函数单元测试（不依赖 Streamlit）。"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config_editor import (
    _empty_card, df_to_card_state, card_state_to_df,
    _compute_table_nos, _update_card, _delete_card,
    _copy_card, _move_card, _insert_after,
)
import pandas as pd


def test_empty_card_defaults():
    card = _empty_card()
    assert card["_level"] == "collapsed"
    assert card["_tableno_overridden"] is False
    assert card["_title_overridden"] is False
    assert "_id" in card


def test_compute_table_nos_basic():
    cards = [
        {**_empty_card(), "Section no": "14.1", "cat": "表"},
        {**_empty_card(), "Section no": "14.1", "cat": "表"},
        {**_empty_card(), "Section no": "14.2", "cat": "表"},
    ]
    result = _compute_table_nos(cards)
    assert result[0]["table no"] == "14.1.1.1"
    assert result[1]["table no"] == "14.1.2.1"
    assert result[2]["table no"] == "14.2.1.1"


def test_compute_table_nos_listing_uses_16_2():
    cards = [
        {**_empty_card(), "Section no": "14.1", "cat": "列表"},
    ]
    result = _compute_table_nos(cards)
    assert result[0]["table no"].startswith("16.2.")


def test_update_card_changes_field():
    cards = [_empty_card()]
    card_id = cards[0]["_id"]
    result = _update_card(cards, card_id, title="新标题")
    assert result[0]["title"] == "新标题"


def test_delete_card_removes_it():
    cards = [_empty_card(), _empty_card()]
    card_id = cards[0]["_id"]
    result = _delete_card(cards, card_id)
    assert len(result) == 1
    assert result[0]["_id"] != card_id


def test_copy_card_inserts_after():
    cards = [_empty_card(), _empty_card()]
    original_id = cards[0]["_id"]
    result = _copy_card(cards, original_id)
    assert len(result) == 3
    assert result[0]["_id"] == original_id
    assert result[1]["_id"] != original_id   # 副本紧随其后
    assert result[1]["_level"] == "collapsed"


def test_move_card_up():
    cards = [_empty_card(), _empty_card()]
    id0, id1 = cards[0]["_id"], cards[1]["_id"]
    result = _move_card(cards, 1, -1)
    assert result[0]["_id"] == id1
    assert result[1]["_id"] == id0


def test_insert_after():
    cards = [_empty_card()]
    original_id = cards[0]["_id"]
    result = _insert_after(cards, original_id)
    assert len(result) == 2
    assert result[0]["_id"] == original_id


def test_card_state_to_df_seqnum():
    cards = [_empty_card(), _empty_card()]
    df = card_state_to_df(cards)
    assert list(df["SeqNum"]) == [1, 2]


def test_df_to_card_state_roundtrip():
    cards = [_empty_card()]
    cards[0]["title"] = "测试"
    cards[0]["Section no"] = "14.1"
    df = card_state_to_df(cards)
    restored = df_to_card_state(df)
    assert restored[0]["title"] == "测试"
    assert restored[0]["Section no"] == "14.1"
    assert restored[0]["_level"] == "collapsed"
```

**Step 2: 运行测试**

```bash
cd /d/shell_tool/web && python -m pytest tests/test_config_editor.py -v
```

Expected: 所有测试 PASS

**Step 3: Commit**

```bash
git add web/tests/test_config_editor.py
git commit -m "test(web): add pure function unit tests for config_editor"
```

---

### Task 6: 验收测试

**Step 1: 启动 Web**

```bash
cd /d/shell_tool && streamlit run web/app.py --server.port 8501
```

**Step 2: 逐项验收**

- [ ] 页面正常加载，无报错
- [ ] 卡片头部只有 6 列：收起▲（展开时）| 🔍 | ▲ | ▼ | + | ⋮ | 摘要/标题
- [ ] 折叠状态：收起▲ 不显示；标题行显示「▶ title...」可点击展开
- [ ] 点击「▶ title」展开卡片到 level1
- [ ] 展开状态：「收起▲」出现
- [ ] 点击「⋮」→ 行内出现「复制」「🗑 删除」；再点「⋮」收起
- [ ] 复制/删除功能正常
- [ ] ▲▼ 排序正常；+ 插入正常
- [ ] 🔍 进入专注模式；「退出🔍」退出
- [ ] 专注模式横幅显示「← 返回表格」按钮
- [ ] Datasets 迷你面板：「📎 dsname 展开▼」可点击；展开后显示数据预览（高度150px）
- [ ] 「展开更多 ▼」expander 内显示 footnote1-7 + Dutoffdate/Source_Data 等字段
- [ ] 从章节表格视图（点击章节父节点进入）点击 title 列按钮 → 切换到卡片视图并聚焦该卡片
- [ ] 聚焦后「← 返回表格」可返回表格视图
- [ ] 保存草稿 / 生成 TFL Shell / 保存并提交 Git 流程不受影响

**Step 3: 最终 Commit（如有遗留修复）**

```bash
git add web/
git commit -m "fix(web): card refactor polish"
```
