# Config 字段显示级别系统设计

**日期：** 2026-05-18  
**范围：** 在 Config 卡片编辑器上叠加三级显示系统；YAML/R 输出结构不变。

---

## 决策摘要

| 议题 | 决策 |
|------|------|
| 级别配置存储 | 新文件 `web/config_display_levels.yaml`，与 config_templates.yaml 分离 |
| required 字段 | 代码硬锁定 6 个，YAML 中即使修改也无效 |
| 卡片展开状态 | `_level` 元字段：`collapsed / level1 / level2 / focus` |
| 专注模式 | session_state._cfg_focus_id 驱动，其他卡片渲染为占位 |
| 筛选 | 只影响渲染可见性，不改变 card_state 顺序/内容 |
| 复制 | 复制为新行，插入当前行之后，table.no 重新编号 |

---

## 数据结构

### config_display_levels.yaml

```yaml
default_collapse: true
field_levels:
  SeqNum:          required
  "Section no":    required
  "Section title": required
  cat:             required
  "table no":      required
  title:           required
  pop:             level1
  footnote1:       level1
  footnote2:       level1
  footnote3:       level1
  footnote4:       level1
  footnote5:       level1
  footnote6:       level1
  footnote7:       level1
  Datasets:        level1
  MacVar:          level1
  Trtlab:          level1
  Dutoffdate:      level2
  Source_Data:     level2
  PgmNotes:        level2
  Subgrp:          level2
  Adcols:          level2
  Varlab:          level2
  Labparm:         level2
  ByseqL:          level2
  RefTFL:          level2
```

### 卡片元数据

```python
{
    # 数据字段（同 CONFIG_COLS）
    ...,
    # 元数据
    "_id": "uuid",
    "_level": "collapsed",        # collapsed | level1 | level2 | focus
    "_title_overridden": False,
    "_tableno_overridden": False,
}
```

### 筛选状态（session_state）

```python
st.session_state._cfg_filter = {
    "section": "",      # "" = 全部
    "cats": [],         # [] = 全部
    "keyword": "",
}
st.session_state._cfg_focus_id = None   # 专注模式卡片 id
```

---

## 展开状态机

```
collapsed ──[展开▼]──► level1 ──[更多▼]──► level2
    ▲                     │                   │
    └──────[收起▲]────────┘───────────────────┘
    
任意状态 ──[🔍]──► focus
focus ──[退出专注]──► level2
```

---

## 卡片头部操作栏

### 收起状态
```
[展开▼] [▲] [▼] [+] [复制] [🗑] [🔍] | Seq | Section.no | cat | table.no | title
```

### 展开（level1/level2）状态
```
[收起▲] [更多▼/收杂▲] [▲] [▼] [+] [复制] [🗑] [🔍] | Seq | …
```

---

## 字段分组渲染

### required（始终显示，在头部行内嵌）
SeqNum, Section no, Section title, cat, table no, title

### level1（展开后显示）
- 行A: Section no（selectbox）/ Section title / cat / table no
- 行B: title（全宽）
- 行C: pop（multiselect）/ MacVar / Datasets
- 行D: Trtlab
- 行E: footnote1-7（折叠 expander，整体算 level1）

### level2（更多后显示）
- 行F: Dutoffdate / Source_Data / PgmNotes
- 行G: Subgrp / Adcols / Varlab / Labparm / ByseqL / RefTFL

---

## 筛选栏

位置：卡片列表顶部。

```
Section: [全部▼]   cat: [表][图][列表]（多选）   关键词: [________]
```

匹配逻辑：
- Section：`card["Section no"] == filter.section`（空 = 不过滤）
- cat：`card["cat"] in filter.cats`（空列表 = 不过滤）
- keyword：模糊匹配 `title` 或 `table no`（大小写不敏感）

不匹配的卡片跳过渲染（`continue`），card_state 本身不变。

---

## 专注模式

- 进入：设 `_cfg_focus_id = card_id`，该卡片 `_level = "focus"`
- 显示：其他卡片渲染为 `st.caption("…")` 占位，不渲染任何字段
- 当前卡片：required + level1 + level2 全部字段展示
- 顶部横幅：`🔍 专注模式中  [退出专注]`
- 退出：清除 `_cfg_focus_id`，卡片 `_level` 回 `level2`

---

## 模板配置界面

app.py Config 模板 expander 改为 3 个 tab：

```
[Section 映射] [pop 选项] [显示级别]
```

"显示级别" tab：
- required 行：显示"必显示 🔒"，不可修改
- 其余行：selectbox，选项 ["一级", "二级", "不显示"]
- [保存显示设置] → 写回 YAML + cache clear

---

## 新增/修改文件

```
web/config_display_levels.yaml   新增
web/config_display_io.py         新增（load/save，@st.cache_data ttl=60）
web/config_editor.py             重写（状态机、筛选、专注模式）
web/app.py                       修改（Config 模板 expander 改为 3 tabs）
```
