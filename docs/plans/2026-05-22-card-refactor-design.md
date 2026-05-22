# 单条卡片重构设计文档

**日期：** 2026-05-22  
**目标：** 重构单条 TFL 卡片编辑界面，解决按钮松散和 Datasets 割裂问题

---

## 一、按钮分组重构

### 折叠状态头部
```
[🔍专注]  │  [▲] [▼] [+]  │  [⋮]   序号 · 章节 · cat · table no · [点击标题展开 ▶]
```
- 折叠时无独立「展开▼」按钮，**点击标题按钮**是主要展开入口
- 标题按钮样式突出（更宽列比例）

### 展开状态头部
```
[收起▲] [🔍专注]  │  [▲] [▼] [+]  │  [⋮]   序号 · 章节 · cat · table no · title摘要
```

### 「⋮」展开行（行内 inline）
点击「⋮」后在头部正下方插入一行：
```
[复制]  [🗑 删除]
```
状态存 `session_state["cfg_menu_open"]`（`set[card_id]`），再点「⋮」收起。

### 列比例
`[0.6, 0.6, 0.3, 0.3, 0.4, 0.4, 0.6, 1.0, 2.5]`  
对应：收起/空, 专注, 上, 下, 插入, 更多, 序号+章节, cat+tableno, title

---

## 二、字段布局（level1 默认展开）

默认行为：**B 方案** — 保持 collapsed 为初始默认，点击标题自动展开到 level1，移除独立「展开▼」按钮。

`_render_level1` 字段分5区：

```
行A: [Section no ▼] [Section title____________] [cat ▼] [table no ⚠️]
行B: [title_________________________________全宽________________]
行C: [pop multiselect______] [MacVar ▼] [Datasets ▼]
行D: [Trtlab_______________________________全宽________________]
行E: [展开更多 ▼]  expander 内：footnote1-7 + level2 字段
```

**关键变化：**
- 原 `_render_level2`（Dutoffdate/Source_Data/PgmNotes/Subgrp 等）挪入「展开更多」expander
- `_level` 状态简化：`"collapsed"` / `"level1"` / `"focus"`，去掉 `"level2"`
- `_render_level2` 作为内部函数保留，由 expander 调用

---

## 三、Datasets 迷你面板

位置：`_render_level1` 内，Trtlab 行之后、「展开更多」之前。

```
📎 demo  [展开▼]
─────────────────────────────────────────
 Class │ Label        │ Order │ Aval
 ──────┼──────────────┼───────┼──────────
       │ 年龄（岁）    │  0    │
       │ 例数          │  1    │ xx
 (高度限制 150px，只读 st.dataframe)
─────────────────────────────────────────
 [编辑完整 Datasets ▶]
```

**实现细节：**
- `_DS_OPEN_KEY = "cfg_ds_panel_open"` → `set[card_id]`
- `📎 {ds_name}` 按钮切换折叠/展开
- 展开时：`st.dataframe(ds_df.head(20), height=150, use_container_width=True)`
- 「编辑完整 Datasets ▶」：设置 `_SELECTED_ID_KEY = card_id` + `st.toast("已关联到下方 Datasets 编辑器 ↓")`
- Datasets 为空时：`st.caption("未关联 Datasets")`

---

## 四、表格视图 → 单条卡片跳转

`section_table.py` `_render_row` title 列（c3）：

```python
# title 列改为跳转按钮
if st.button(cur_title[:30] or "（空）", key=f"tbl_goto_{card_id}_{ver}"):
    st.session_state["section_nav_view_mode"] = "card"
    st.session_state[_FOCUS_KEY] = card_id
    st.session_state[_CARD_STATE_KEY] = _update_card(
        st.session_state[_CARD_STATE_KEY], card_id, _level="level1"
    )
    st.rerun()
```

卡片视图 focus 横幅增加「← 返回表格视图」：
```python
if focus_id:
    col_info, col_back = st.columns([4, 1])
    with col_info:
        st.info("🔍 专注模式中 — 点击「退出🔍」退出")
    with col_back:
        if st.button("← 返回表格视图"):
            st.session_state["section_nav_view_mode"] = "table"
            st.session_state[_FOCUS_KEY] = None
            st.rerun()
```

---

## 五、改动文件汇总

| 文件 | 改动 |
|------|------|
| `web/config_editor.py` | `_render_header` 重构按钮分组；`_render_level1` 加 Datasets 面板 + 「展开更多」expander；`_render_card` 简化 level 逻辑 |
| `web/section_table.py` | `_render_row` title 列改为跳转按钮 |
| `web/app.py` | focus 横幅加「← 返回表格视图」按钮（移入 `render_config_editor` 内） |
