# Section 章节导航树 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在 Config 编辑界面左侧增加固定章节导航树，整体改为左右分栏布局，左侧按 Section 分组展示所有 TFL 条目，点击可筛选/定位右侧卡片列表。

**Architecture:** 新建 `web/section_nav.py` 负责导航树渲染逻辑（纯视图层，不触碰数据结构）；在 `web/app.py` 将 Config 主表区域改为 `st.columns([1, 3])` 左右分栏；在 `web/config_editor.py` 增加 scroll-to 定位支持（通过 session_state `_cfg_focus_id` + `_level` 已有机制复用）。不改动数据层（`config_card_state`、保存流程、YAML 序列化）。

**Tech Stack:** Streamlit columns + session_state，Python 标准库

---

### Task 1: 新建 section_nav.py — 分组逻辑

**Files:**
- Create: `web/section_nav.py`

**Step 1: 实现 group_by_section**

```python
# web/section_nav.py
"""左侧章节导航树 —— 纯视图层，不修改数据。"""
from __future__ import annotations
import re
import streamlit as st

_NAV_STATE_KEY = "section_nav_state"   # { sec_no: collapsed:bool }
_NAV_FILTER_KEY = "section_nav_filter" # { "section": str, "scroll_to": str|None }


def _nav_state() -> dict:
    if _NAV_STATE_KEY not in st.session_state:
        st.session_state[_NAV_STATE_KEY] = {}
    return st.session_state[_NAV_STATE_KEY]


def _nav_filter() -> dict:
    if _NAV_FILTER_KEY not in st.session_state:
        st.session_state[_NAV_FILTER_KEY] = {"section": "", "scroll_to": None}
    return st.session_state[_NAV_FILTER_KEY]


def _sec_sort_key(sec_no: str) -> tuple:
    """将 '14.1.2' 拆成 (14, 1, 2) 用于数值排序。"""
    parts = re.split(r"[.\-]", sec_no.strip())
    result = []
    for p in parts:
        try:
            result.append(int(p))
        except ValueError:
            result.append(p)
    return tuple(result)


def group_by_section(card_state: list[dict]) -> list[dict]:
    """
    将 card_state 按 Section no 分组，返回有序列表：
    [
      {
        "section_no": "14.1",
        "section_title": "人口学",
        "items": [card_dict, ...],   # 保留原始 card 引用
      },
      ...
    ]
    """
    groups: dict[str, dict] = {}
    for card in card_state:
        sec = str(card.get("Section no") or "").strip()
        if not sec:
            sec = "（无章节）"
        if sec not in groups:
            groups[sec] = {
                "section_no": sec,
                "section_title": str(card.get("Section title") or "").strip(),
                "items": [],
            }
        groups[sec]["items"].append(card)

    return sorted(groups.values(), key=lambda g: _sec_sort_key(g["section_no"]))
```

**Step 2: 手动验证逻辑正确性**

在 Python REPL 中快速测试：
```python
cards = [
    {"Section no": "14.2", "Section title": "安全性", "table no": "14.2.1.1", "title": "TEAE"},
    {"Section no": "14.1", "Section title": "人口学", "table no": "14.1.1.1", "title": "基线"},
    {"Section no": "14.1", "Section title": "人口学", "table no": "14.1.1.2", "title": "体征"},
]
result = group_by_section(cards)
assert result[0]["section_no"] == "14.1"
assert len(result[0]["items"]) == 2
assert result[1]["section_no"] == "14.2"
print("OK")
```

**Step 3: Commit**

```bash
git add web/section_nav.py
git commit -m "feat(web): add section_nav.py with group_by_section logic"
```

---

### Task 2: section_nav.py — 渲染 UI

**Files:**
- Modify: `web/section_nav.py`（追加 render_section_nav 函数）

**Step 1: 实现 render_section_nav**

在文件末尾追加：

```python
def render_section_nav(card_state: list[dict]) -> None:
    """
    渲染左侧章节导航树。
    副作用：更新 session_state[_NAV_FILTER_KEY]，供右侧卡片列表读取。
    """
    groups = group_by_section(card_state)
    nav = _nav_state()
    filt = _nav_filter()
    cur_section = filt.get("section", "")

    # "全部" 按钮
    all_active = cur_section == ""
    if st.button(
        f"{'● ' if all_active else '  '}全部（{len(card_state)}）",
        key="nav_all",
        use_container_width=True,
    ):
        filt["section"] = ""
        filt["scroll_to"] = None
        st.session_state[_NAV_FILTER_KEY] = filt
        st.rerun()

    st.divider()

    for group in groups:
        sec_no = group["section_no"]
        sec_title = group["section_title"]
        items = group["items"]
        count = len(items)
        is_collapsed = nav.get(sec_no, False)
        is_active_sec = cur_section == sec_no

        # 章节标题行：展开/折叠 toggle + 点击筛选
        toggle_icon = "▼" if not is_collapsed else "▶"
        active_mark = "● " if is_active_sec else "  "
        sec_label = f"{toggle_icon}{active_mark}{sec_no}"
        if sec_title:
            sec_label += f" {sec_title[:10]}"
        sec_label += f" ({count})"

        col_sec, col_toggle = st.columns([5, 1])
        with col_sec:
            if st.button(sec_label, key=f"nav_sec_{sec_no}", use_container_width=True):
                # 点击章节 → 筛选该章节，折叠状态切换为展开
                filt["section"] = sec_no
                filt["scroll_to"] = None
                nav[sec_no] = False  # 展开
                st.session_state[_NAV_FILTER_KEY] = filt
                st.session_state[_NAV_STATE_KEY] = nav
                st.rerun()

        with col_toggle:
            if st.button("⊟" if not is_collapsed else "⊞", key=f"nav_toggle_{sec_no}"):
                nav[sec_no] = not is_collapsed
                st.session_state[_NAV_STATE_KEY] = nav
                st.rerun()

        # 子条目列表（仅展开时显示）
        if not is_collapsed:
            for card in items:
                card_id = card.get("_id", "")
                tbl_no = str(card.get("table no") or "")
                title = str(card.get("title") or "")
                label_text = tbl_no
                if title:
                    label_text += f" {title[:20]}"
                    if len(title) > 20:
                        label_text += "…"

                scroll_active = filt.get("scroll_to") == card_id
                item_label = f"{'● ' if scroll_active else '  '}{label_text}"

                if st.button(item_label, key=f"nav_item_{card_id}", use_container_width=True):
                    # 点击条目 → 筛选该章节 + scroll_to 该卡片
                    filt["section"] = sec_no
                    filt["scroll_to"] = card_id
                    nav[sec_no] = False
                    st.session_state[_NAV_FILTER_KEY] = filt
                    st.session_state[_NAV_STATE_KEY] = nav
                    st.rerun()
```

**Step 2: Commit**

```bash
git add web/section_nav.py
git commit -m "feat(web): add render_section_nav UI function"
```

---

### Task 3: config_editor.py — 支持 scroll_to 定位

**Files:**
- Modify: `web/config_editor.py`

**Step 1: 在 render_config_editor 中读取 scroll_to 并展开目标卡片**

找到 `render_config_editor` 函数入口（约 L581），在 `_ensure_card_state` 调用之后、渲染卡片循环之前，加入如下逻辑：

```python
# 处理 scroll_to 定位请求（来自章节导航树）
from section_nav import _NAV_FILTER_KEY
nav_filt = st.session_state.get(_NAV_FILTER_KEY, {})
scroll_to_id = nav_filt.get("scroll_to")
if scroll_to_id:
    # 展开目标卡片到 level1（如果当前是 collapsed）
    card_state_now = st.session_state[_CARD_STATE_KEY]
    for c in card_state_now:
        if c["_id"] == scroll_to_id and c.get("_level") == "collapsed":
            st.session_state[_CARD_STATE_KEY] = _update_card(
                card_state_now, scroll_to_id, _level="level1"
            )
            break
    # 消费 scroll_to，避免重复触发
    nav_filt["scroll_to"] = None
    st.session_state[_NAV_FILTER_KEY] = nav_filt
```

将这段代码插入在 `focus_id: str | None = st.session_state.get(_FOCUS_KEY)` 赋值行之后。

**Step 2: 在卡片循环中读取 nav section 筛选**

找到卡片渲染循环（约 L611）：
```python
    for i, card in enumerate(card_state):
        if not focus_id and not _card_visible(card, filt):
            continue
```

修改为：
```python
    for i, card in enumerate(card_state):
        if not focus_id and not _card_visible(card, filt):
            continue
        # 章节导航树筛选（与原筛选栏独立叠加）
        nav_section = st.session_state.get(_NAV_FILTER_KEY, {}).get("section", "")
        if not focus_id and nav_section and str(card.get("Section no") or "") != nav_section:
            continue
```

**Step 3: Commit**

```bash
git add web/config_editor.py
git commit -m "feat(web): support scroll_to and nav section filter in config_editor"
```

---

### Task 4: app.py — 改为左右分栏，接入导航树

**Files:**
- Modify: `web/app.py`

**Step 1: 添加 import**

在文件顶部 import 区域末尾追加：
```python
from section_nav import render_section_nav
```

**Step 2: 改造 Config 主表区域**

找到 app.py 中的：
```python
    # ── Config 主表 ─────────────────────────────────────────────────────────
    st.subheader("Config 主表")
    ...
    edited_config, selected_idx = render_config_editor(...)
```

将这段替换为左右分栏：

```python
    # ── Config 主表（左右分栏）──────────────────────────────────────────────
    st.subheader("Config 主表")

    from config_editor import _CARD_STATE_KEY as _CFG_CARD_KEY
    _nav_col, _edit_col = st.columns([1, 3], gap="small")

    with _nav_col:
        # 章节导航树（读取当前 card_state，在卡片列表渲染前先渲染导航）
        _current_card_state = st.session_state.get(_CFG_CARD_KEY, [])
        render_section_nav(_current_card_state)

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

注意：原来 `dataset_keys` 和 `cfg_templates` 的赋值移到 `with _edit_col:` 块内，删除原来在分栏外的那两行赋值。

**Step 3: Commit**

```bash
git add web/app.py
git commit -m "feat(web): split config editor into left nav + right card list layout"
```

---

### Task 5: 验收测试

**Step 1: 启动 Web**

```bash
cd d:\shell_tool
streamlit run web/app.py --server.port 8501
```

**Step 2: 逐项验收**

- [ ] 页面正常加载，无报错
- [ ] 左侧显示"全部（N）"按钮 + 各 Section 分组
- [ ] Section 按 14.1 / 14.2 / 14.3 / 16.2 数值排序
- [ ] 点击章节名 → 右侧只显示该章节的 TFL 卡片
- [ ] 点击"全部" → 右侧显示所有卡片
- [ ] 章节 ⊟/⊞ 按钮可折叠/展开子条目列表
- [ ] 点击子条目 → 右侧筛选至该章节，对应卡片自动展开到 level1
- [ ] 折叠/展开状态持久（切换 section 后返回，状态保留）
- [ ] 保存草稿 / 生成 TFL Shell / 保存并提交 Git 流程不受影响

**Step 3: 最终 Commit（如有遗留修复）**

```bash
git add web/
git commit -m "fix(web): section nav tree polish"
```
