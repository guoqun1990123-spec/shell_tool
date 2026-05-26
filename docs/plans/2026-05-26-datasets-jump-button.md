# Datasets 跳转按钮实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在 Config 卡片的 collapsed 摘要行和 level1 展开态各加一个「🗂 编辑 Datasets」按钮，点击后直接跳转到 Datasets 标签页并定位到对应数据表。

**Architecture:** 仅修改 `web/config_editor.py`。按钮点击时写入 `st.session_state.selected_row`（int 索引）和 `st.session_state.active_tab = "datasets"`，然后 `st.rerun()` 触发 app.py 的标签页切换。

**Tech Stack:** Streamlit session_state, Python

---

## 背景

### 现有相关代码

- `web/config_editor.py:239` — `_render_header()` 的 7 列布局（collapsed 摘要行）
- `web/config_editor.py:304-314` — collapsed 行的展开按钮（`c_info` 列）
- `web/config_editor.py:466-477` — level1 的 Datasets selectbox（`rC3` 列）
- `web/config_editor.py:497-507` — level1 已有「编辑完整 Datasets ▶」按钮，但只设 `selected_row`，未切换标签

### session_state 关键字段

- `st.session_state.selected_row`：int 或 None，Datasets 标签用来定位当前数据表
- `st.session_state.active_tab`：`"config"` | `"datasets"` | `"overview"` | `"templates"`
- `_SELECTED_ID_KEY = "_cfg_selected_id"`：config_editor 内部用，标记选中卡片 id

---

## Task 1：修复 level1 已有按钮，使其切换标签页

**Files:**
- Modify: `web/config_editor.py:497-507`

**Step 1: 写测试（手动验证用例）**

打开 Web 界面，展开任意有 Datasets 的卡片（level1），展开「📎 xxx 展开▼」面板后，点击「编辑完整 Datasets ▶」。

预期（改前）：toast 提示，但标签页不切换，仍停在 Config 章节。

**Step 2: 修改实现**

定位 `web/config_editor.py` 第 502-505 行：

```python
                if st.button("编辑完整 Datasets ▶", key=f"cfg_ds_edit_{card_id}_{version}"):
                    st.session_state[_SELECTED_ID_KEY] = card_id
                    st.toast("已关联到下方 Datasets 编辑器 ↓")
                    st.rerun()
```

替换为：

```python
                if st.button("🗂 编辑 Datasets", key=f"cfg_ds_edit_{card_id}_{version}"):
                    st.session_state[_SELECTED_ID_KEY] = card_id
                    # 把 idx 写入 selected_row 供 Datasets 标签定位
                    # （idx 是外层 _render_card 的参数，需要传入）
                    st.session_state["selected_row"] = _card_idx_in_state(card_id)
                    st.session_state["active_tab"] = "datasets"
                    st.rerun()
```

但 `_render_level1` 当前没有 `idx` 参数。需要在 Task 2 中统一处理，这里先用辅助函数 `_card_idx_in_state`。

**Step 3: 添加辅助函数**

在 `config_editor.py` 顶部函数区（紧接 `_ds_open()` 之后）添加：

```python
def _card_idx_in_state(card_id: str) -> int | None:
    """返回卡片在当前 card_state 中的下标，找不到返回 None。"""
    state = st.session_state.get(_CARD_STATE_KEY, [])
    for i, c in enumerate(state):
        if c["_id"] == card_id:
            return i
    return None
```

**Step 4: 验证**

展开任意有 Datasets 的卡片，展开迷你面板，点击「🗂 编辑 Datasets」。

预期：页面跳转到「🗂 Datasets」标签页，顶部显示 `当前选中：SeqNum=xx，Datasets='xxx'`。

**Step 5: Commit**

```bash
git add web/config_editor.py
git commit -m "feat(web): 编辑Datasets按钮跳转到Datasets标签页"
```

---

## Task 2：在 collapsed 摘要行加「🗂」跳转按钮

**Files:**
- Modify: `web/config_editor.py:238-314`（`_render_header` 函数）

**Step 1: 理解现有布局**

`_render_header` 第 239-241 行定义 7 列布局：
```python
c_collapse, c_focus, c_up, c_dn, c_ins, c_more, c_info = st.columns(
    [0.55, 0.45, 0.28, 0.28, 0.28, 0.28, 4.5]
)
```

collapsed 行在 `c_info` 列显示展开按钮（第 306-314 行）。

**Step 2: 扩展为 8 列，加入「🗂」列**

将 7 列布局改为 8 列，在 `c_info` 之前插入 `c_ds`：

```python
c_collapse, c_focus, c_up, c_dn, c_ins, c_more, c_ds, c_info = st.columns(
    [0.55, 0.45, 0.28, 0.28, 0.28, 0.28, 0.45, 4.5]
)
```

**Step 3: 在 `c_ds` 列渲染按钮**

在 `c_more` 块结束后（第 302 行之后），`c_info` 块之前，添加：

```python
    with c_ds:
        cur_ds_hdr = str(card.get("Datasets", "") or "")
        if st.button("🗂", key=f"cfg_ds_jump_{card_id}_{version}",
                     help=f"编辑 Datasets: {cur_ds_hdr}" if cur_ds_hdr else "编辑 Datasets",
                     disabled=not cur_ds_hdr):
            st.session_state[_SELECTED_ID_KEY] = card_id
            st.session_state["selected_row"] = _card_idx_in_state(card_id)
            st.session_state["active_tab"] = "datasets"
            st.rerun()
```

注意：`_render_header` 没有 `idx` 参数，用 Task 1 中添加的 `_card_idx_in_state` 即可。

**Step 4: 验证 collapsed 行**

折叠一张有 Datasets 的卡片，应看到 collapsed 行多了一个「🗂」图标按钮（有 Datasets 时可点，无时灰显）。点击后跳转 Datasets 标签页且正确定位。

**Step 5: 验证无 Datasets 的卡片**

没有填写 Datasets 字段的卡片，「🗂」按钮应显示为灰色不可点击（`disabled=True`）。

**Step 6: Commit**

```bash
git add web/config_editor.py
git commit -m "feat(web): collapsed摘要行加🗂快速跳转Datasets按钮"
```

---

## Task 3：level1 行 C 的 Datasets selectbox 旁也加按钮

**Files:**
- Modify: `web/config_editor.py:434-477`（`_render_level1` 行 C）

**Step 1: 将行 C 从 3 列改为 4 列**

当前第 435 行：
```python
        rC1, rC2, rC3 = st.columns([2.5, 1.5, 1.5])
```

改为：
```python
        rC1, rC2, rC3, rC4 = st.columns([2.5, 1.5, 1.5, 0.5])
```

**Step 2: 在 `rC4` 渲染跳转按钮**

在 `rC3`（Datasets selectbox）块结束后（第 477 行之后），添加：

```python
        with rC4:
            st.write("")  # 对齐 label 高度
            if st.button("🗂", key=f"cfg_ds_jump_l1_{card_id}_{version}",
                         help=f"编辑 Datasets: {cur_ds}" if cur_ds else "编辑 Datasets",
                         disabled=not cur_ds):
                st.session_state[_SELECTED_ID_KEY] = card_id
                st.session_state["selected_row"] = _card_idx_in_state(card_id)
                st.session_state["active_tab"] = "datasets"
                st.rerun()
```

**Step 3: 验证**

展开任意卡片到 level1，Datasets 下拉框右侧应出现「🗂」按钮。选中一个 Datasets 后点击，跳转到 Datasets 标签并正确定位。

**Step 4: 运行测试**

```bash
cd web && python -m pytest tests/ -v
```

预期：全部通过（本次改动只涉及 UI 渲染，不触及纯函数逻辑，测试应不受影响）。

**Step 5: Commit**

```bash
git add web/config_editor.py
git commit -m "feat(web): level1 Datasets字段旁加🗂快速跳转按钮"
```

---

## 验收标准

1. collapsed 行：有 Datasets 时「🗂」可点，无时灰显
2. level1 行 C：Datasets 下拉右侧「🗂」可点，无 Datasets 时灰显
3. level1 迷你面板：「🗂 编辑 Datasets」按钮文字更新，点击跳转
4. 三处按钮点击后均：切换到 Datasets 标签、顶部显示正确的 SeqNum 和 Datasets 名
5. `pytest tests/ -v` 全部通过
