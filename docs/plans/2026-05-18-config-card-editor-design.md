# Config 卡片编辑器设计

**日期：** 2026-05-18  
**范围：** 替换 Config 主表的 `st.data_editor` 为卡片式编辑器；YAML/R 端输出结构不变。

---

## 决策摘要

| 议题 | 决策 |
|------|------|
| YAML 兼容性 | 完全兼容，输出仍为 CONFIG_COLS 列名 |
| 模板存储 | `web/config_templates.yaml`，Web 端可视化编辑 |
| 行选择器 | 卡片点击选中，去掉旧下拉选择器 |

---

## 架构

### 新增文件
```
web/config_templates.yaml      # Section 映射 + pop 选项
web/config_templates_io.py     # 加载/保存（@st.cache_data ttl=60）
web/config_editor.py           # 卡片编辑器组件
```

### 修改文件
```
web/app.py    # 替换 st.data_editor + 行选择器，新增模板管理 expander
web/schema.py # 新增 CONFIG_SECTION_MAP, CONFIG_POP_OPTIONS 常量
```

### 不变文件
`yaml_io.py`, `excel_io.py`, `validators.py`, R 端全部代码。

---

## 数据模型

### Card state
存于 `st.session_state.config_card_state`，类型 `list[dict]`。

每行字段：
```python
{
    # 所有 CONFIG_COLS 字段（与现有完全一致）
    "SeqNum": 1,
    "Section no": "14.1",
    "Section title": "参与者特征",
    "cat": "表",
    "table no": "14.1.1.1",
    "title": "",
    "pop": "所有筛选参与者",
    "MacVar": "",
    "Datasets": "",
    # ... 其余 CONFIG_COLS 字段

    # 元数据（不写入 YAML）
    "_id": "uuid",
    "_expanded": False,
    "_title_overridden": False,   # Section title 是否已手动覆盖
    "_tableno_overridden": False, # table no 是否已手动覆盖
}
```

### 转换
| 方向 | 逻辑 |
|------|------|
| DataFrame → card state | 逐行转换，补充 `_id`/`_expanded=False`/`_title_overridden=False`/`_tableno_overridden=False` |
| card state → DataFrame | 过滤 `_*` 字段，按 SeqNum 顺序打平；SeqNum 按顺序重排 1,2,3... |

---

## 卡片 UI 布局

### 收起状态
```
[⊞] [▲][▼] | Seq:1 | 14.1 | 表 | 14.1.1.1 | 年龄分布分析    [🗑]
```

### 展开状态
```
[⊟] [▲][▼] | Seq:1 | 14.1 参与者特征 | 表 | 14.1.1.1       [🗑]
────────────────────────────────────────────────────────────
行1: [Section.no ▼]  [Section.title________]  [cat ▼]  [table.no____]
行2: [title_________________________________]
行3: [pop 多选▼_____] [MacVar____] [Datasets 多选▼]
行4: [footnote1___________________________]
行5: [Dutoffdate____] [Source_Data____] [PgmNotes____]
```

---

## 自动编号规则

**SeqNum：** 按卡片顺序从 1 递增，移动后自动重排。

**table.no：**
- 按 `Section no` 分组，同组内按 cat 出现顺序编号
- 格式：`{Section.no}.{组内序号}.1`
- "列表" cat → 前缀固定 `16.2`
- 手动修改后 `_tableno_overridden=True`，不再自动更新
- 覆盖值与自动值不同时，table.no 输入框显示橙色提示

**Section title：**
- 选择 `Section no` 时自动填充（来自模板）
- 手动修改后 `_title_overridden=True`
- 再次改变 `Section no` 时弹确认：是否重置 title

---

## config_templates.yaml 格式

```yaml
section_map:
  "14.1": "参与者特征"
  "14.2": "疗效分析"
  "14.3": "安全性分析"
  "16.2": "列表"
pop_options:
  - 所有筛选参与者
  - ITT
  - mITT
  - FAS
  - SS
  - EAS
  - IS
  - PKS
  - PDS
```

---

## 模板管理 expander

```
▼ Config 模板配置
  Section 映射：
  │ 14.1  →  参与者特征  [🗑] │
  │ 14.2  →  疗效分析    [🗑] │
  [+ 添加]   [保存]

  人群（pop）选项：
  │ 所有筛选参与者  [🗑] │
  │ ITT            [🗑] │
  [+ 添加]   [保存]
```

---

## app.py 改动范围

1. 删除：`st.data_editor` 调用、`_build_config_column_config`、下拉行选择器
2. 新增：`render_config_editor()` 调用，返回 `(edited_df, selected_idx)`
3. 新增：Config 模板管理 expander（与 Datasets 模板 expander 并列）
4. 保留：`_merge_edited`、`_do_save`、YAML 预览、校验逻辑（直接用返回的 df）
