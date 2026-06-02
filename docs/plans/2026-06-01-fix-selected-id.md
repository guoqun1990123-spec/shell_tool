# Fix selected_row → selected_id Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将 `selected_row`（卡片下标）替换为 `selected_id`（`_id` UUID），消除卡片增删/移动后下标漂移导致 Datasets 标签页读到错误数据集的 Bug。

**Architecture:** 外科手术式修改，涉及三个文件。`config_editor.py` 负责写入 `selected_id`（已有 `_SELECTED_ID_KEY` 常量），`app.py` 负责读取并通过 `_id` 从 card_state 中查找对应 card。`render_config_editor` 返回值从 `(df, idx)` 改为 `(df, id_or_none)`，`app.py` 中消费处同步适配。

**Tech Stack:** Python 3, Streamlit, pandas

---

### 当前问题全貌

**写入侧（`config_editor.py`）**：三处 🗂 按钮都同时写了 `_SELECTED_ID_KEY`（存 `card_id`）和 `selected_row`（存 `_card_idx_in_state(card_id)`）。`_SELECTED_ID_KEY` 已经是正确的 UUID，多余地写了下标。

**读取侧（`app.py`）**：Datasets tab 只读 `selected_row`（下标），用 `iloc[sel_idx_ds]` 取 card，完全忽略了已有的 `_SELECTED_ID_KEY`。

**`render_config_editor` 返回值**：返回 `(df, selected_idx)`，`app.py` 存入 `session_state.selected_row`。

**修复方向**：
1. `config_editor.py` 的三处 🗂 按钮不再写 `selected_row`（保留写 `_SELECTED_ID_KEY`）
2. `render_config_editor` 返回 `(df, selected_id_or_none)`（UUID 字符串）
3. `app.py` 的 Config tab 和 Datasets tab 全部改用 `selected_id`（UUID），通过遍历 card_state 查找对应 card
4. `_init_state` 和 `_do_load`/新建空白 中把 `selected_row` 改名为 `selected_id`

---

### Task 1：`config_editor.py` — 三处 🗂 按钮不再写 `selected_row`，`render_config_editor` 返回 `selected_id`

**Files:**
- Modify: `web/config_editor.py`

**Step 1: 读取并确认三处写 `selected_row` 的位置**

搜索 `selected_row`，确认以下三处（行号仅供参考，以实际文件为准）：

- `_render_header` 中的头部 🗂 按钮（`c_ds` 列，约第 319 行）
- `_render_level1` 中的 Level1 🗂 按钮（`rC4` 列，约第 505 行）
- `_render_level1` 中的「🗂 编辑 Datasets」按钮（`cfg_ds_edit`，约第 535 行）

**Step 2: 删除三处的 `selected_row` 写入**

三处都有类似代码：
```python
st.session_state[_SELECTED_ID_KEY] = card_id
st.session_state["selected_row"] = _card_idx_in_state(card_id)   # ← 删除这行
st.session_state["active_tab"] = "datasets"
```
每处只删除 `selected_row` 那一行，其余不变。

**Step 3: 修改 `render_config_editor` 末尾返回值**

找到函数末尾（约第 820-831 行）：
```python
    final_state: list[dict] = st.session_state[_CARD_STATE_KEY]
    df = card_state_to_df(final_state)

    selected_id = st.session_state.get(_SELECTED_ID_KEY)
    selected_idx: int | None = None
    if selected_id:
        for i, c in enumerate(final_state):
            if c["_id"] == selected_id:
                selected_idx = i
                break

    return df, selected_idx
```
改为直接返回 `selected_id`（UUID 字符串或 None），删除下标转换逻辑：
```python
    final_state: list[dict] = st.session_state[_CARD_STATE_KEY]
    df = card_state_to_df(final_state)
    selected_id = st.session_state.get(_SELECTED_ID_KEY)
    return df, selected_id
```

同时更新函数 docstring（约第 745 行）：
```python
    """Render card-based config editor with 3-level display system.

    Returns (edited_df, selected_card_id).
    """
```

**Step 4: Commit**

```bash
cd d:/shell_tool
git add web/config_editor.py
git commit -m "refactor: config_editor 不再写 selected_row，render_config_editor 返回 card _id"
```

---

### Task 2：`app.py` — 全面替换 `selected_row` 为 `selected_id`

**Files:**
- Modify: `web/app.py`

**Step 1: 读取 `app.py` 中所有涉及 `selected_row` 的位置**

共 6 处，逐一处理：

**处 1：`_init_state()`**（约第 79-80 行）
```python
    if "selected_row" not in st.session_state:
        st.session_state.selected_row = None
```
改为：
```python
    if "selected_id" not in st.session_state:
        st.session_state.selected_id = None
```

**处 2：`_do_load()`**（约第 136 行）
```python
        st.session_state.selected_row = None
```
改为：
```python
        st.session_state.selected_id = None
```

**处 3：新建空白按钮**（约第 194 行）
```python
        st.session_state.selected_row = None
```
改为：
```python
        st.session_state.selected_id = None
```

**处 4：Config tab — 表格视图分支**（约第 308 行）
```python
                selected_idx = st.session_state.selected_row
```
改为：
```python
                selected_id = st.session_state.get("selected_id")
```

**处 5：Config tab — 卡片视图分支**（约第 310-315 行）
```python
                edited_config, selected_idx = render_config_editor(
                    st.session_state.config_df,
                    dataset_keys,
                    cfg_templates,
                )
                st.session_state.selected_row = selected_idx
```
改为：
```python
                edited_config, selected_id = render_config_editor(
                    st.session_state.config_df,
                    dataset_keys,
                    cfg_templates,
                )
                st.session_state.selected_id = selected_id
```

**处 6：Datasets tab — 读取 selected_id 并查找对应 card**（约第 322-332 行）

当前代码：
```python
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
```
改为（通过 `_id` 直接在 card_state 中查找，不依赖下标）：
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

注意：`_cs2df` 和 `edited_config_ds` 的构建代码（约第 319-321 行）可以删除，因为 Datasets tab 不再需要 DataFrame 中转：
```python
        # 以下两行删除：
        _cs = st.session_state.get(_CFG_CARD_KEY, [])
        from config_editor import card_state_to_df as _cs2df
        edited_config_ds = _cs2df(_cs)
```

**Step 2: 确认表格视图分支中 `selected_id` 的处理**

表格视图分支（约第 308 行改后）现在只是读取 `selected_id`，但 `render_section_table` 不修改 `selected_id`（它通过 `_SELECTED_ID_KEY` 写入，已在 Task 1 保留）。表格视图跳转到卡片 focus 模式时，也是写 `_SELECTED_ID_KEY = card_id`，这里不涉及 `selected_id`（Datasets 用途），两者是不同的 key，不会混淆。

**Step 3: Commit**

```bash
cd d:/shell_tool
git add web/app.py
git commit -m "fix: selected_row 改为 selected_id(UUID)，消除卡片增删后下标漂移导致 Datasets 读错 card"
```

---

### Task 3：验证与回归检查

**Step 1: 手动验证修复效果**

1. 加载一个 YAML 文件，Config 有多个卡片
2. 点击某卡片的 🗂 按钮，跳到 Datasets 标签页，确认显示的是正确的 SeqNum 和 Datasets 名
3. 返回 Config 标签页，在刚才那个卡片**之前**插入一个新卡片（使原卡片下标 +1）
4. 不重新点 🗂，直接切换到 Datasets 标签页
5. 确认仍显示**原来那个卡片**的信息，而非新插入卡片（下标 0）的信息

**Step 2: 回归验证**

- 「新建空白」后 Datasets 标签页显示「请先选中」提示 ✓
- 加载新文件后 `selected_id` 被清除，Datasets 标签页显示「请先选中」提示 ✓
- 卡片视图中点 🗂 → 正确跳转到对应 dataset ✓
- 表格视图中点 🗂（嵌入编辑按钮）→ 正确跳转 ✓

**Step 3: Push**

```bash
cd d:/shell_tool
git push origin master
```
