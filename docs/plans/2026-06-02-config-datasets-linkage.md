# Config-Datasets Linkage Fixes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 修复 Config 与 Datasets 标签页之间的 9 个联动问题，包括导航栏选中同步 Datasets、返回按钮、共用数据集提示、新建自动关联、删除卡片清除 selected_id、MacVar 兼容提示、数据集重命名、顶部信息补全、预览缓存失效优化。

**Architecture:** 所有修改集中在 `web/app.py`、`web/config_editor.py`、`web/section_nav.py` 三个文件。核心机制是将 `selected_id` 的写入点从「只有 🗂 按钮」扩展到「导航树点击条目」，并在各个操作节点补充缺失的状态同步和用户提示。

**Tech Stack:** Python 3, Streamlit

---

## 关键上下文（实现者必读）

### session_state 关键 key

| Key | 含义 |
|-----|------|
| `selected_id` | 当前选中 Config 卡片的 `_id`（UUID），Datasets tab 用此查找卡片 |
| `section_nav_selected_id` | 导航树当前高亮的条目 `_id`，与 `selected_id` 当前是独立的 |
| `active_tab` | `"config"` \| `"datasets"` \| `"overview"` \| `"templates"` |
| `_tab_switch_req` | 递增触发 tabs widget 重建，实现标签页跳转 |
| `_CARD_STATE_KEY` = `"config_card_state"` | Config 所有卡片 list[dict] |

### Datasets tab 读取 selected_id 的位置（app.py 约第 317-328 行）

```python
sel_id_ds = st.session_state.get("selected_id")
_cs_for_ds = st.session_state.get(_CFG_CARD_KEY, [])
sel_card = next((c for c in _cs_for_ds if c.get("_id") == sel_id_ds), None) if sel_id_ds else None

if sel_card is not None:
    ds_name = str(sel_card.get("Datasets", "") or "").strip()
    macvar = str(sel_card.get("MacVar", "") or "").strip()
    seq_no = sel_card.get("SeqNum", "?")
    st.caption(f"当前选中：SeqNum={seq_no}，Datasets='{ds_name}'，MacVar='{macvar}'")
else:
    ds_name = ""
    st.info("请先在「Config章节」标签页中点击某行以选中，再切换此标签查看数据表。")
```

### 导航树点击条目的位置（section_nav.py 约第 175-184 行）

```python
if st.button(item_label, key=f"nav_item_{card_id}", use_container_width=True):
    filt["section"] = sec_no
    filt["scroll_to"] = card_id
    nav[sec_no] = False
    st.session_state[_NAV_FILTER_KEY] = filt
    st.session_state[_NAV_STATE_KEY] = nav
    st.session_state[_VIEW_MODE_KEY] = "card"
    st.session_state["section_nav_selected_id"] = card_id
    st.session_state["_cfg_focus_id"] = None
    st.rerun()
```

---

## Task 1：导航树点击条目时同步 `selected_id`

**Files:**
- Modify: `web/section_nav.py`

**背景：** 导航树点击条目时写 `section_nav_selected_id` 但不写 `selected_id`，导致切换到 Datasets 标签页仍显示旧卡片的数据集。

**Step 1: 找到导航树条目按钮回调（约第 175-184 行），在 `st.session_state["section_nav_selected_id"] = card_id` 之后追加**

```python
                if st.button(item_label, key=f"nav_item_{card_id}", use_container_width=True):
                    filt["section"] = sec_no
                    filt["scroll_to"] = card_id
                    nav[sec_no] = False
                    st.session_state[_NAV_FILTER_KEY] = filt
                    st.session_state[_NAV_STATE_KEY] = nav
                    st.session_state[_VIEW_MODE_KEY] = "card"
                    st.session_state["section_nav_selected_id"] = card_id
                    st.session_state["selected_id"] = card_id   # 新增：同步 Datasets tab
                    st.session_state["_cfg_focus_id"] = None
                    st.rerun()
```

**Step 2: Commit**
```bash
cd d:/shell_tool
git add web/section_nav.py
git commit -m "feat: 导航树点击条目时同步 selected_id，Datasets tab 随之更新"
```

---

## Task 2：删除 Config 卡片时清除 `selected_id`

**Files:**
- Modify: `web/config_editor.py`

**背景：** 删除卡片时清除了 `_SELECTED_ID_KEY` 和 `_FOCUS_KEY`，但没有清除 `selected_id`（Datasets tab 用的 key），导致 Datasets tab 仍尝试查找已不存在的卡片，显示「请先选中」的提示，用户困惑。

**Step 1: 找到删除卡片的回调（搜索 `cfg_del_`，约第 340-348 行）**

当前：
```python
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

改为（追加清除 `selected_id` 和 `section_nav_selected_id`）：
```python
            if st.button("🗑 删除", key=f"cfg_del_{card_id}_{version}"):
                menu.discard(card_id)
                st.session_state[_MENU_OPEN_KEY] = menu
                if st.session_state.get(_SELECTED_ID_KEY) == card_id:
                    st.session_state[_SELECTED_ID_KEY] = None
                if st.session_state.get(_FOCUS_KEY) == card_id:
                    st.session_state[_FOCUS_KEY] = None
                if st.session_state.get("selected_id") == card_id:
                    st.session_state["selected_id"] = None
                if st.session_state.get("section_nav_selected_id") == card_id:
                    st.session_state["section_nav_selected_id"] = None
                st.session_state[_CARD_STATE_KEY] = _delete_card(card_state, card_id)
                st.rerun()
```

**Step 2: Commit**
```bash
cd d:/shell_tool
git add web/config_editor.py
git commit -m "fix: 删除 Config 卡片时同步清除 selected_id 和 section_nav_selected_id"
```

---

## Task 3：Datasets 顶部补全显示信息 + 返回按钮

**Files:**
- Modify: `web/app.py`

**背景：** 顶部只显示 SeqNum/Datasets/MacVar，缺少 table no 和 title，用户不知道自己在编辑哪张表。同时缺少「返回 Config」的快捷路径。

**Step 1: 找到 Datasets tab 顶部信息区（约第 321-328 行）**

当前：
```python
        if sel_card is not None:
            ds_name = str(sel_card.get("Datasets", "") or "").strip()
            macvar = str(sel_card.get("MacVar", "") or "").strip()
            seq_no = sel_card.get("SeqNum", "?")
            st.caption(f"当前选中：SeqNum={seq_no}，Datasets='{ds_name}'，MacVar='{macvar}'")
        else:
            ds_name = ""
            st.info("请先在「Config章节」标签页中点击某行以选中，再切换此标签查看数据表。")
```

改为（补全 table no + title，加返回按钮）：
```python
        if sel_card is not None:
            ds_name = str(sel_card.get("Datasets", "") or "").strip()
            macvar = str(sel_card.get("MacVar", "") or "").strip()
            seq_no = sel_card.get("SeqNum", "?")
            tbl_no = str(sel_card.get("table no", "") or "").strip()
            title  = str(sel_card.get("title", "") or "").strip()
            title_short = (title[:30] + "…") if len(title) > 30 else title

            _info_col, _back_col = st.columns([5, 1])
            with _info_col:
                st.caption(
                    f"**{tbl_no}** {title_short}  ·  "
                    f"SeqNum={seq_no}  ·  Datasets=`{ds_name}`  ·  MacVar=`{macvar}`"
                )
            with _back_col:
                if st.button("← Config", key="btn_back_to_config",
                             help="返回 Config 章节并定位到该卡片"):
                    sel_id = st.session_state.get("selected_id")
                    if sel_id:
                        from config_editor import _CARD_STATE_KEY as _cfgkey, _update_card
                        _cs = st.session_state.get(_cfgkey, [])
                        _cs = _update_card(_cs, sel_id, _level="focus")
                        st.session_state[_cfgkey] = _cs
                        st.session_state["_cfg_focus_id"] = sel_id
                        st.session_state["section_nav_view_mode"] = "card"
                    st.session_state["active_tab"] = "config"
                    st.session_state["_tab_switch_req"] = st.session_state.get("_tab_switch_req", 0) + 1
                    st.rerun()
        else:
            ds_name = ""
            st.info("请先在「Config章节」标签页中点击某行以选中，再切换此标签查看数据表。")
```

**Step 2: Commit**
```bash
cd d:/shell_tool
git add web/app.py
git commit -m "feat: Datasets 顶部补全 table no/title，增加「← Config」返回按钮"
```

---

## Task 4：共用数据集提示

**Files:**
- Modify: `web/app.py`

**背景：** 多个 Config 行的 `Datasets` 字段填同一个数据集名时，编辑一处会影响全部，但用户无感知。

**Step 1: 在 Datasets tab 中，`ds_name` 确定后、编辑器渲染前，统计有多少个 Config 行共用该数据集**

找到约第 353 行 `if ds_name and ds_name in st.session_state.datasets:` 之前，插入：

```python
        # 共用数据集提示
        if ds_name:
            _cs_all = st.session_state.get(_CFG_CARD_KEY, [])
            _shared_cards = [
                c for c in _cs_all
                if str(c.get("Datasets") or "").strip() == ds_name
            ]
            if len(_shared_cards) > 1:
                _shared_labels = [
                    str(c.get("table no") or c.get("SeqNum") or "?")
                    for c in _shared_cards
                ]
                st.warning(
                    f"⚠️ 此数据集被 **{len(_shared_cards)}** 张表共用："
                    f" {', '.join(_shared_labels[:5])}"
                    + ("…" if len(_shared_labels) > 5 else "")
                    + "。修改将影响所有引用此数据集的 TFL。"
                )
```

**Step 2: Commit**
```bash
cd d:/shell_tool
git add web/app.py
git commit -m "feat: Datasets 顶部显示共用数据集提示，列出所有引用该数据集的 TFL"
```

---

## Task 5：新建数据集后自动关联到当前 Config 行

**Files:**
- Modify: `web/app.py`

**背景：** 新建数据集后，当前选中 Config 行的 `Datasets` 字段为空时，应自动填入新数据集名，省去切回 Config 手动选择的步骤。

**Step 1: 找到新建数据表按钮回调（约第 342-351 行）**

当前：
```python
            if st.button("新建数据表", key="btn_add_ds"):
                if new_ds_name and new_ds_name not in st.session_state.datasets:
                    if copy_from != "— 空白 —" and copy_from in st.session_state.datasets:
                        st.session_state.datasets[new_ds_name] = st.session_state.datasets[copy_from].copy()
                    else:
                        is_list = new_ds_name == "list"
                        st.session_state.datasets[new_ds_name] = (
                            _empty_dataset_list() if is_list else _empty_dataset_table()
                        )
                    st.rerun()
```

改为（新建后若当前 Config 行 Datasets 为空则自动关联）：
```python
            if st.button("新建数据表", key="btn_add_ds"):
                if new_ds_name and new_ds_name not in st.session_state.datasets:
                    if copy_from != "— 空白 —" and copy_from in st.session_state.datasets:
                        st.session_state.datasets[new_ds_name] = st.session_state.datasets[copy_from].copy()
                    else:
                        is_list = new_ds_name == "list"
                        st.session_state.datasets[new_ds_name] = (
                            _empty_dataset_list() if is_list else _empty_dataset_table()
                        )
                    # 若当前选中的 Config 行 Datasets 字段为空，自动关联新建的数据集
                    _cur_sel_id = st.session_state.get("selected_id")
                    if _cur_sel_id:
                        from config_editor import _CARD_STATE_KEY as _cfgkey2, _update_card as _uc2
                        _cs2 = st.session_state.get(_cfgkey2, [])
                        _cur_card2 = next((c for c in _cs2 if c["_id"] == _cur_sel_id), None)
                        if _cur_card2 and not str(_cur_card2.get("Datasets") or "").strip():
                            st.session_state[_cfgkey2] = _uc2(_cs2, _cur_sel_id, Datasets=new_ds_name)
                            st.toast(f"✅ 已自动关联到当前 TFL 的 Datasets 字段")
                    st.rerun()
```

**Step 2: Commit**
```bash
cd d:/shell_tool
git add web/app.py
git commit -m "feat: 新建数据集后自动关联到当前 Config 行（仅当 Datasets 字段为空时）"
```

---

## Task 6：MacVar 改变时检查数据集兼容性并提示

**Files:**
- Modify: `web/config_editor.py`

**背景：** MacVar 从 `PStab` 改为 `RptList` 时，当前 `Datasets` 字段仍指向卡片编辑器结构的数据集，但 `RptList` 需要 `list` 键下的 listing 结构，R 端渲染才会报错，用户无提前感知。

**兼容性规则：**
- `RptList` 需要 `Datasets` 字段指向 `list` 键，或者 datasets 中存在 `list` 键
- 其他 MacVar 类型对数据集结构无特殊要求

**Step 1: 找到 MacVar selectbox 的变更回调（约第 473-484 行）**

当前：
```python
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
```

改为（改变后检测兼容性）：
```python
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
                # 兼容性检查：RptList 需要 list 数据集
                if new_macvar == "RptList":
                    _datasets = st.session_state.get("datasets", {})
                    _cur_ds = str(card.get("Datasets") or "").strip()
                    if "list" not in _datasets:
                        st.warning(
                            "⚠️ MacVar 已改为 RptList，但 datasets 中尚无 `list` 数据集，"
                            "请在 Datasets 标签页新建名为 `list` 的数据表。"
                        )
                    elif _cur_ds and _cur_ds != "list":
                        st.warning(
                            f"⚠️ MacVar 已改为 RptList，当前 Datasets=`{_cur_ds}`，"
                            "RptList 使用 `list` 数据集，建议将 Datasets 字段改为 `list`。"
                        )
                st.rerun()
```

**Step 2: Commit**
```bash
cd d:/shell_tool
git add web/config_editor.py
git commit -m "feat: MacVar 改为 RptList 时检查数据集兼容性并弹警告"
```

---

## Task 7：数据集重命名功能（重命名时同步更新所有 Config 行）

**Files:**
- Modify: `web/app.py`

**背景：** 目前无重命名入口。新增一个「重命名」文本输入，重命名后同步更新 `session_state.datasets` 的键、以及所有 Config 卡片中引用该数据集名的 `Datasets` 字段。

**Step 1: 在新建数据表区域旁边增加重命名控件**

找到约第 330-351 行的新建数据表区域，在 `if ds_name and ds_name in st.session_state.datasets:` 之前（约第 353 行），插入重命名控件：

```python
        # 数据集重命名
        if ds_name and ds_name in st.session_state.datasets:
            with st.expander("✏️ 重命名此数据集", expanded=False):
                _rename_col1, _rename_col2 = st.columns([3, 1])
                with _rename_col1:
                    _new_name = st.text_input(
                        "新名称", value=ds_name,
                        key=f"rename_ds_{ds_name}",
                        label_visibility="collapsed",
                    )
                with _rename_col2:
                    if st.button("确认重命名", key=f"btn_rename_ds_{ds_name}",
                                 disabled=not _new_name.strip() or _new_name == ds_name):
                        _new_name = _new_name.strip()
                        if _new_name in st.session_state.datasets:
                            st.error(f"数据集名 `{_new_name}` 已存在，请换一个名称。")
                        else:
                            # 1. 迁移数据
                            st.session_state.datasets[_new_name] = st.session_state.datasets.pop(ds_name)
                            # 2. 迁移 card state
                            from dataset_editor import state_key as _ds_state_key
                            _old_card_key = _ds_state_key(ds_name)
                            _new_card_key = _ds_state_key(_new_name)
                            if _old_card_key in st.session_state:
                                st.session_state[_new_card_key] = st.session_state.pop(_old_card_key)
                            _old_ver_key = f"_ds_version_{ds_name}"
                            _new_ver_key = f"_ds_version_{_new_name}"
                            if _old_ver_key in st.session_state:
                                st.session_state[_new_ver_key] = st.session_state.pop(_old_ver_key)
                            # 3. 更新所有 Config 卡片的 Datasets 字段
                            from config_editor import _CARD_STATE_KEY as _cfgkey3
                            _cs3 = st.session_state.get(_cfgkey3, [])
                            st.session_state[_cfgkey3] = [
                                {**c, "Datasets": _new_name}
                                if str(c.get("Datasets") or "").strip() == ds_name
                                else c
                                for c in _cs3
                            ]
                            st.toast(f"✅ 已将数据集 `{ds_name}` 重命名为 `{_new_name}`，并同步更新了所有引用")
                            st.rerun()
```

**Step 2: Commit**
```bash
cd d:/shell_tool
git add web/app.py
git commit -m "feat: Datasets 标签页增加重命名功能，自动同步所有 Config 行的 Datasets 字段"
```

---

## Task 8：预览缓存在 Datasets 编辑时主动失效

**Files:**
- Modify: `web/app.py`

**背景：** 当前预览缓存签名只用行数+列名，单元格内容变化（编辑 Aval/Label）后签名不变，静态预览不刷新。修复方案：每次 Datasets tab 写回 `session_state.datasets[ds_name]` 时，清除所有引用该数据集的 Config 卡片的预览缓存 key。

**Step 1: 找到 Datasets tab 中写回 DataFrame 的位置**

有两处：
- `list` 类型：约第 368 行 `st.session_state.datasets[ds_name] = edited_ds`
- 卡片类型：约第 396 行 `st.session_state.datasets[ds_name] = result_df`

在两处写回后各插入缓存失效逻辑（提取为辅助函数避免重复）。

**Step 2: 在 `_do_load` 函数附近（约第 122 行后）定义辅助函数**

```python
def _invalidate_preview_cache(ds_name: str) -> None:
    """清除所有引用该数据集的 Config 卡片的静态预览缓存。"""
    from config_editor import _CARD_STATE_KEY as _cfgkey_inv
    _cs_inv = st.session_state.get(_cfgkey_inv, [])
    for _c in _cs_inv:
        if str(_c.get("Datasets") or "").strip() == ds_name:
            _cid = _c["_id"]
            for _k in (f"_preview_html_{_cid}", f"_preview_sig_{_cid}"):
                if _k in st.session_state:
                    del st.session_state[_k]
```

**Step 3: 在两处写回后调用**

`list` 类型写回后（约第 368 行）：
```python
                    st.session_state.datasets[ds_name] = edited_ds
                    _invalidate_preview_cache(ds_name)
```

卡片类型写回后（约第 396 行）：
```python
                    st.session_state.datasets[ds_name] = result_df
                    _invalidate_preview_cache(ds_name)
```

**Step 4: Commit**
```bash
cd d:/shell_tool
git add web/app.py
git commit -m "fix: Datasets 编辑后主动失效对应 Config 卡片的静态预览缓存"
```

---

## Task 9：最终验证与 Push

**Step 1: 手动验证清单**

1. **导航树联动**：在左侧导航树点击某个条目 → 切到 Datasets 标签页 → 显示该条目对应的数据集
2. **删除不残留**：删除一个 Config 卡片后切到 Datasets → 显示「请先选中」而非报错
3. **返回按钮**：在 Datasets 标签页点「← Config」→ 跳回 Config 并 focus 到对应卡片
4. **顶部信息**：Datasets 顶部显示 table no + title（前30字）+ SeqNum + Datasets + MacVar
5. **共用提示**：两个 Config 行共用同一数据集时，顶部显示黄色警告及引用列表
6. **新建自动关联**：选中一个 Datasets 为空的 Config 行 → 切到 Datasets → 新建数据集 → 切回 Config → 该行 Datasets 字段已填入
7. **MacVar 兼容警告**：将某行 MacVar 改为 `RptList` 且无 `list` 数据集时，显示警告
8. **重命名同步**：展开重命名 expander，输入新名称确认 → 数据集键名改变，所有 Config 行 Datasets 字段同步更新
9. **预览缓存失效**：编辑数据集 Label/Aval → 切到 Config 预览 tab → 预览内容已更新（不显示旧数据）

**Step 2: Push**
```bash
cd d:/shell_tool
git push origin master
```
