# 章节批量编辑表格视图 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 点击左侧章节父节点时，右侧切换为紧凑表格视图，支持行内即时编辑（table no / cat / title / pop / Datasets）、行展开为 level1 卡片、多行勾选批量修改。

**Architecture:** 新建 `web/section_table.py` 提供 `render_section_table()` 函数（纯视图层，复用 `config_editor.py` 的 `_update_card` / `_compute_table_nos` / `_render_level1`）；修改 `web/section_nav.py` 在章节父节点点击时写入 `view_mode=table`；修改 `web/app.py` 的 `_edit_col` 按 `view_mode` 路由到表格视图或原有卡片视图。数据层（`_CARD_STATE_KEY`）不变，YAML 序列化流程不变。

**Tech Stack:** Streamlit columns + session_state，复用 config_editor.py 内部函数

---

### Task 1: section_nav.py — 章节点击写入 view_mode

**Files:**
- Modify: `web/section_nav.py`

新增两个常量并修改章节父节点点击逻辑。

**Step 1: 在文件顶部常量区追加两个新常量**

找到 `_NAV_FILTER_KEY = "section_nav_filter"` 这行，在其**后**追加：

```python
_VIEW_MODE_KEY = "section_nav_view_mode"      # "card" | "table"
_TABLE_SECTION_KEY = "section_nav_table_section"  # 当前表格视图的 section_no
```

**Step 2: 修改章节父节点按钮点击逻辑**

找到 `render_section_nav` 中章节按钮点击的 if 块：
```python
            if st.button(sec_label, key=f"nav_sec_{sec_no}", use_container_width=True):
                filt["section"] = sec_no
                filt["scroll_to"] = None
                nav[sec_no] = False
                st.session_state[_NAV_FILTER_KEY] = filt
                st.session_state[_NAV_STATE_KEY] = nav
                st.rerun()
```

替换为：
```python
            if st.button(sec_label, key=f"nav_sec_{sec_no}", use_container_width=True):
                filt["section"] = sec_no
                filt["scroll_to"] = None
                nav[sec_no] = False
                st.session_state[_NAV_FILTER_KEY] = filt
                st.session_state[_NAV_STATE_KEY] = nav
                st.session_state[_VIEW_MODE_KEY] = "table"
                st.session_state[_TABLE_SECTION_KEY] = sec_no
                st.rerun()
```

**Step 3: 修改子条目点击逻辑，切换回卡片视图**

找到子条目按钮点击的 if 块：
```python
                if st.button(item_label, key=f"nav_item_{card_id}", use_container_width=True):
                    filt["section"] = sec_no
                    filt["scroll_to"] = card_id
                    nav[sec_no] = False
                    st.session_state[_NAV_FILTER_KEY] = filt
                    st.session_state[_NAV_STATE_KEY] = nav
                    st.rerun()
```

替换为：
```python
                if st.button(item_label, key=f"nav_item_{card_id}", use_container_width=True):
                    filt["section"] = sec_no
                    filt["scroll_to"] = card_id
                    nav[sec_no] = False
                    st.session_state[_NAV_FILTER_KEY] = filt
                    st.session_state[_NAV_STATE_KEY] = nav
                    st.session_state[_VIEW_MODE_KEY] = "card"
                    st.rerun()
```

**Step 4: "全部"按钮点击时也切回卡片视图**

找到 "全部" 按钮点击：
```python
        filt["section"] = ""
        filt["scroll_to"] = None
        st.session_state[_NAV_FILTER_KEY] = filt
        st.rerun()
```

替换为：
```python
        filt["section"] = ""
        filt["scroll_to"] = None
        st.session_state[_NAV_FILTER_KEY] = filt
        st.session_state[_VIEW_MODE_KEY] = "card"
        st.rerun()
```

**Step 5: 验证语法**

```bash
python -c "import sys; sys.path.insert(0,'d:/shell_tool/web'); import section_nav; print('OK')"
```
预期：`OK`

**Step 6: Commit**

```bash
git -C "d:/shell_tool" add web/section_nav.py
git -C "d:/shell_tool" commit -m "feat(web): write view_mode to session_state on nav click"
```

---

### Task 2: 新建 section_table.py — 核心骨架

**Files:**
- Create: `web/section_table.py`

**Step 1: 创建文件骨架**

```python
# web/section_table.py
"""章节批量编辑表格视图。"""
from __future__ import annotations
import streamlit as st

from config_editor import (
    _CARD_STATE_KEY,
    _update_card,
    _compute_table_nos,
    _delete_card,
    _render_level1,
    CAT_OPTIONS,
)
from schema import VALID_MACVAR

_CHECKED_KEY = "table_checked_ids"      # set[str] — 当前勾选的 card_id
_EXPANDED_KEY = "table_expanded_rows"   # set[str] — 就地展开的 card_id
_VERSION_KEY = "table_editor_version"   # int — 强制 widget key 刷新


def _checked() -> set:
    if _CHECKED_KEY not in st.session_state:
        st.session_state[_CHECKED_KEY] = set()
    return st.session_state[_CHECKED_KEY]


def _expanded() -> set:
    if _EXPANDED_KEY not in st.session_state:
        st.session_state[_EXPANDED_KEY] = set()
    return st.session_state[_EXPANDED_KEY]


def _version() -> int:
    return st.session_state.get(_VERSION_KEY, 0)


def render_section_table(
    card_state: list[dict],
    sec_no: str,
    dataset_keys: list[str],
    cfg_templates: dict,
) -> None:
    """渲染章节批量编辑表格视图（主入口）。"""
    # 过滤出当前章节的卡片（保留在整体 card_state 中的引用顺序）
    sec_cards = [c for c in card_state if str(c.get("Section no") or "").strip() == sec_no]

    _render_header(sec_no, sec_cards, dataset_keys, cfg_templates)
    _render_bulk_bar(sec_cards, dataset_keys, cfg_templates)
    _render_column_header()

    ver = _version()
    for card in sec_cards:
        _render_row(card, dataset_keys, cfg_templates, ver)
```

**Step 2: 验证 import 无循环依赖**

```bash
python -c "
import sys; sys.path.insert(0,'d:/shell_tool/web')
import section_table
print('OK')
"
```
预期：`OK`

**Step 3: Commit**

```bash
git -C "d:/shell_tool" add web/section_table.py
git -C "d:/shell_tool" commit -m "feat(web): add section_table.py skeleton"
```

---

### Task 3: section_table.py — 表头区 + 批量操作栏

**Files:**
- Modify: `web/section_table.py`

在文件末尾追加以下三个函数：

**Step 1: 追加 _render_header**

```python
def _render_header(
    sec_no: str,
    sec_cards: list[dict],
    dataset_keys: list[str],
    cfg_templates: dict,
) -> None:
    """章节标题行 + [+ 添加TFL] 按钮。"""
    # 取第一张卡片的 Section title
    sec_title = ""
    if sec_cards:
        sec_title = str(sec_cards[0].get("Section title") or "").strip()

    col_title, col_add = st.columns([5, 1])
    with col_title:
        display = f"{sec_no} {sec_title}".strip() if sec_title else sec_no
        st.subheader(display)
    with col_add:
        if st.button("＋ 添加TFL", key=f"tbl_add_{sec_no}"):
            from config_editor import _empty_card, _insert_after
            card_state = st.session_state[_CARD_STATE_KEY]
            # 在该章节最后一张卡片后插入，并预填 Section no
            if sec_cards:
                last_id = sec_cards[-1]["_id"]
                new_state = _insert_after(card_state, last_id)
                # 找到新卡片（最后插入的空卡片）并设置 Section no
                for c in new_state:
                    if c["_id"] not in {x["_id"] for x in card_state}:
                        new_state = _update_card(new_state, c["_id"],
                                                 **{"Section no": sec_no})
                        break
            else:
                from config_editor import _add_card
                new_state = _add_card(card_state)
                for c in new_state:
                    if c["_id"] not in {x["_id"] for x in card_state}:
                        new_state = _update_card(new_state, c["_id"],
                                                 **{"Section no": sec_no})
                        break
            st.session_state[_CARD_STATE_KEY] = new_state
            st.session_state[_VERSION_KEY] = _version() + 1
            st.rerun()
```

**Step 2: 追加 _render_bulk_bar**

```python
def _render_bulk_bar(
    sec_cards: list[dict],
    dataset_keys: list[str],
    cfg_templates: dict,
) -> None:
    """批量操作栏：全选 / 删除 / 修改pop / 修改Datasets。"""
    checked = _checked()
    sec_ids = {c["_id"] for c in sec_cards}
    all_checked = bool(sec_ids) and sec_ids <= checked

    pop_options: list[str] = cfg_templates.get("pop_options", [])

    col_all, col_del, col_pop, col_ds, col_spacer = st.columns([0.8, 1.2, 1.5, 1.5, 3])

    with col_all:
        new_all = st.checkbox("全选", value=all_checked, key=f"tbl_chk_all_{id(sec_cards)}")
        if new_all != all_checked:
            if new_all:
                checked |= sec_ids
            else:
                checked -= sec_ids
            st.session_state[_CHECKED_KEY] = checked
            st.rerun()

    with col_del:
        sel_in_sec = checked & sec_ids
        if st.button(f"删除选中({len(sel_in_sec)})", key="tbl_bulk_del",
                     disabled=not sel_in_sec):
            if sel_in_sec:
                confirm_key = "tbl_confirm_del"
                st.session_state[confirm_key] = True

    # 删除确认弹窗
    if st.session_state.get("tbl_confirm_del"):
        sel_in_sec = checked & sec_ids
        st.warning(f"确认删除选中的 {len(sel_in_sec)} 条 TFL？")
        cy, cn = st.columns(2)
        with cy:
            if st.button("确认删除", key="tbl_del_yes", type="primary"):
                state = st.session_state[_CARD_STATE_KEY]
                for cid in list(sel_in_sec):
                    state = _delete_card(state, cid)
                st.session_state[_CARD_STATE_KEY] = state
                checked -= sel_in_sec
                st.session_state[_CHECKED_KEY] = checked
                st.session_state["tbl_confirm_del"] = False
                st.rerun()
        with cn:
            if st.button("取消", key="tbl_del_no"):
                st.session_state["tbl_confirm_del"] = False
                st.rerun()

    with col_pop:
        sel_in_sec = checked & sec_ids
        if sel_in_sec and pop_options:
            new_pop = st.selectbox("批量设pop", ["—"] + pop_options,
                                   key="tbl_bulk_pop", label_visibility="collapsed")
            if new_pop and new_pop != "—":
                state = st.session_state[_CARD_STATE_KEY]
                for cid in sel_in_sec:
                    state = _update_card(state, cid, pop=new_pop)
                st.session_state[_CARD_STATE_KEY] = state
                st.rerun()
        else:
            st.caption("修改pop▼")

    with col_ds:
        sel_in_sec = checked & sec_ids
        if sel_in_sec and dataset_keys:
            new_ds = st.selectbox("批量设Datasets", ["—"] + dataset_keys,
                                  key="tbl_bulk_ds", label_visibility="collapsed")
            if new_ds and new_ds != "—":
                state = st.session_state[_CARD_STATE_KEY]
                for cid in sel_in_sec:
                    state = _update_card(state, cid, Datasets=new_ds)
                st.session_state[_CARD_STATE_KEY] = state
                st.rerun()
        else:
            st.caption("修改Datasets▼")
```

**Step 3: 追加 _render_column_header**

```python
def _render_column_header() -> None:
    """列标题行（纯文本标签）。"""
    st.divider()
    h0, h1, h2, h3, h4, h5, h6 = st.columns([0.5, 1.5, 0.8, 3.0, 1.5, 1.5, 0.5])
    with h0: st.caption("☑")
    with h1: st.caption("table no")
    with h2: st.caption("cat")
    with h3: st.caption("title")
    with h4: st.caption("pop")
    with h5: st.caption("Datasets")
    with h6: st.caption("⊞")
    st.divider()
```

**Step 4: 验证语法**

```bash
python -c "
import sys; sys.path.insert(0,'d:/shell_tool/web')
import section_table
print('OK')
"
```

**Step 5: Commit**

```bash
git -C "d:/shell_tool" add web/section_table.py
git -C "d:/shell_tool" commit -m "feat(web): add section_table header and bulk operation bar"
```

---

### Task 4: section_table.py — 行渲染（_render_row）

**Files:**
- Modify: `web/section_table.py`

在文件末尾追加 `_render_row` 函数：

**Step 1: 追加 _render_row**

```python
def _render_row(
    card: dict,
    dataset_keys: list[str],
    cfg_templates: dict,
    ver: int,
) -> None:
    """渲染单行：checkbox + 5列即时编辑字段 + 展开按钮。"""
    card_id = card["_id"]
    checked = _checked()
    expanded = _expanded()
    pop_options: list[str] = cfg_templates.get("pop_options", [])

    is_checked = card_id in checked
    is_expanded = card_id in expanded

    c0, c1, c2, c3, c4, c5, c6 = st.columns([0.5, 1.5, 0.8, 3.0, 1.5, 1.5, 0.5])

    # 勾选框
    with c0:
        new_chk = st.checkbox("", value=is_checked, key=f"tbl_chk_{card_id}_{ver}",
                              label_visibility="collapsed")
        if new_chk != is_checked:
            if new_chk:
                checked.add(card_id)
            else:
                checked.discard(card_id)
            st.session_state[_CHECKED_KEY] = checked
            st.rerun()

    # table no
    with c1:
        cur_tbl = str(card.get("table no") or "")
        tbl_overridden = bool(card.get("_tableno_overridden"))
        tbl_label = "⚠️" if tbl_overridden else "table no"
        new_tbl = st.text_input(tbl_label, value=cur_tbl,
                                key=f"tbl_tblno_{card_id}_{ver}",
                                label_visibility="collapsed")
        if new_tbl != cur_tbl:
            state = st.session_state[_CARD_STATE_KEY]
            st.session_state[_CARD_STATE_KEY] = _update_card(
                state, card_id,
                **{"table no": new_tbl, "_tableno_overridden": bool(new_tbl.strip())},
            )
            st.rerun()
        if tbl_overridden:
            if st.button("↩重置", key=f"tbl_reset_tbl_{card_id}_{ver}"):
                state = st.session_state[_CARD_STATE_KEY]
                new_state = _update_card(state, card_id, _tableno_overridden=False)
                st.session_state[_CARD_STATE_KEY] = _compute_table_nos(new_state)
                st.rerun()

    # cat
    with c2:
        cur_cat = str(card.get("cat") or "")
        new_cat = st.selectbox("cat", options=CAT_OPTIONS,
                               index=CAT_OPTIONS.index(cur_cat) if cur_cat in CAT_OPTIONS else 0,
                               key=f"tbl_cat_{card_id}_{ver}",
                               label_visibility="collapsed")
        if new_cat != cur_cat:
            state = st.session_state[_CARD_STATE_KEY]
            st.session_state[_CARD_STATE_KEY] = _update_card(state, card_id, cat=new_cat)
            st.rerun()

    # title
    with c3:
        cur_title = str(card.get("title") or "")
        new_title = st.text_input("title", value=cur_title,
                                  key=f"tbl_title_{card_id}_{ver}",
                                  label_visibility="collapsed")
        if new_title != cur_title:
            state = st.session_state[_CARD_STATE_KEY]
            st.session_state[_CARD_STATE_KEY] = _update_card(state, card_id, title=new_title)
            st.rerun()

    # pop
    with c4:
        cur_pop = str(card.get("pop") or "")
        pop_opts = [""] + pop_options
        new_pop = st.selectbox("pop", options=pop_opts,
                               index=pop_opts.index(cur_pop) if cur_pop in pop_opts else 0,
                               key=f"tbl_pop_{card_id}_{ver}",
                               label_visibility="collapsed")
        if new_pop != cur_pop:
            state = st.session_state[_CARD_STATE_KEY]
            st.session_state[_CARD_STATE_KEY] = _update_card(state, card_id, pop=new_pop)
            st.rerun()

    # Datasets
    with c5:
        cur_ds = str(card.get("Datasets") or "")
        ds_opts = [""] + dataset_keys
        new_ds = st.selectbox("Datasets", options=ds_opts,
                              index=ds_opts.index(cur_ds) if cur_ds in ds_opts else 0,
                              key=f"tbl_ds_{card_id}_{ver}",
                              label_visibility="collapsed")
        if new_ds != cur_ds:
            state = st.session_state[_CARD_STATE_KEY]
            st.session_state[_CARD_STATE_KEY] = _update_card(state, card_id, Datasets=new_ds)
            st.rerun()

    # 展开按钮
    with c6:
        expand_icon = "⊟" if is_expanded else "⊞"
        if st.button(expand_icon, key=f"tbl_expand_{card_id}_{ver}"):
            if is_expanded:
                expanded.discard(card_id)
            else:
                expanded.add(card_id)
            st.session_state[_EXPANDED_KEY] = expanded
            st.rerun()

    # 就地展开区域：复用 config_editor 的 _render_level1
    if is_expanded:
        with st.container():
            card_state_now = st.session_state[_CARD_STATE_KEY]
            # 取最新的 card 数据
            cur_card = next((c for c in card_state_now if c["_id"] == card_id), card)
            _render_level1(cur_card, card_state_now, dataset_keys, cfg_templates, ver)

    st.divider()
```

**Step 2: 验证语法**

```bash
python -c "
import sys; sys.path.insert(0,'d:/shell_tool/web')
import section_table
print('OK')
"
```

**Step 3: Commit**

```bash
git -C "d:/shell_tool" add web/section_table.py
git -C "d:/shell_tool" commit -m "feat(web): add _render_row with inline editing and expand"
```

---

### Task 5: app.py — 接入表格视图路由

**Files:**
- Modify: `web/app.py`

**Step 1: 追加 import**

找到顶部 import 区，在 `from section_nav import render_section_nav` 行**后**追加：

```python
from section_table import render_section_table
```

**Step 2: 修改 _edit_col 区域**

找到 `with _edit_col:` 块（约 L190）：

```python
    with _edit_col:
        dataset_keys = list(st.session_state.datasets.keys())
        cfg_templates = load_config_templates()

        edited_config, selected_idx = render_config_editor(
            st.session_state.config_df,
            dataset_keys,
            cfg_templates,
        )
        st.session_state.selected_row = selected_idx
```

替换为：

```python
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
            # 表格视图下保持 edited_config 与 card_state 同步
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
```

**Step 3: 验证语法**

```bash
python -c "
import sys; sys.path.insert(0,'d:/shell_tool/web')
import py_compile; py_compile.compile('d:/shell_tool/web/app.py')
print('syntax OK')
"
```

**Step 4: Commit**

```bash
git -C "d:/shell_tool" add web/app.py
git -C "d:/shell_tool" commit -m "feat(web): route to section_table view when nav_view_mode=table"
```

---

### Task 6: config_editor.py — 导出 _render_level1 供外部使用

**Files:**
- Modify: `web/config_editor.py`

`_render_level1` 目前是私有函数（下划线前缀），`section_table.py` 需要 import 它。Python 并不强制限制，但需要确认 import 时没有问题。

**Step 1: 验证可以直接 import**

```bash
python -c "
import sys; sys.path.insert(0,'d:/shell_tool/web')
from config_editor import _render_level1, _update_card, _compute_table_nos, _delete_card, CAT_OPTIONS
print('import OK')
"
```

预期：`import OK`（Python 不限制下划线函数的 import）

**Step 2: 如果报错 ImportError**

仅在报错时执行：在 `config_editor.py` 末尾添加别名：
```python
# 供 section_table.py 使用的导出别名
render_level1_for_table = _render_level1
```
然后在 `section_table.py` 中改为 `from config_editor import render_level1_for_table as _render_level1`。

**Step 3: Commit（仅在有修改时）**

```bash
git -C "d:/shell_tool" add web/config_editor.py web/section_table.py
git -C "d:/shell_tool" commit -m "fix(web): export _render_level1 alias for section_table"
```

---

### Task 7: 验收测试

**Step 1: 启动应用**

```bash
streamlit run "d:/shell_tool/web/app.py" --server.port 8502 --server.headless true &
sleep 8 && curl -s http://localhost:8502/_stcore/health
```
预期：`ok`

**Step 2: Playwright 验收脚本**

```python
# /tmp/table_test.py
import asyncio
from playwright.async_api import async_playwright

BASE = "http://localhost:8502"

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1400, "height": 900})
        await page.goto(BASE, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(2000)

        # 加载 sample YAML
        await page.locator('label').filter(has_text="YAML").first.click()
        await page.wait_for_timeout(500)
        await page.locator('[data-testid="stSelectbox"]').first.click()
        await page.wait_for_timeout(300)
        opt = page.locator('li[role="option"]').filter(has_text="sample")
        if await opt.count() > 0:
            await opt.first.click()
        await page.locator('button').filter(has_text="加载").first.click()
        await page.wait_for_timeout(3000)

        # 点击左侧第一个章节按钮（含 ▼）
        sec_btn = page.locator('button').filter(has_text="▼").first
        await sec_btn.click()
        await page.wait_for_timeout(1500)
        await page.screenshot(path="/tmp/tbl_01_table_view.png")
        print("[1] 点击章节后截图")

        # 验证表格视图元素
        tbl_no_inputs = page.locator('input[type="text"]')
        count = await tbl_no_inputs.count()
        print(f"[2] text input 数量: {count} (表格行内编辑)")

        # 截图全貌
        await page.screenshot(path="/tmp/tbl_02_full.png")

        # 点击全部返回卡片视图
        await page.locator('button').filter(has_text="全部").first.click()
        await page.wait_for_timeout(1000)
        await page.screenshot(path="/tmp/tbl_03_back_to_card.png")
        print("[3] 返回卡片视图截图")

        await browser.close()
        print("DONE")

asyncio.run(main())
```

运行：`python /tmp/table_test.py`

**Step 3: 逐项人工验收（看截图）**

- [ ] 点击章节父节点 → 右侧切换为表格视图（含列标题 table no / cat / title / pop / Datasets）
- [ ] 每行有 checkbox、text_input（table no、title）、selectbox（cat、pop、Datasets）
- [ ] 修改 table no → 显示 ⚠️ 标签 + [↩重置] 按钮
- [ ] 点击 ⊞ 按钮 → 行下方展开 level1 字段
- [ ] 批量：全选 checkbox 可勾选所有行
- [ ] 点击左侧"全部" → 右侧切回卡片视图
- [ ] 点击左侧子条目 → 右侧切回卡片视图并 scroll_to 定位

**Step 4: Commit（如有修复）**

```bash
git -C "d:/shell_tool" add web/
git -C "d:/shell_tool" commit -m "fix(web): section table view polish"
```
