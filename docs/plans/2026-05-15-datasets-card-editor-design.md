# Datasets 卡片式编辑器设计

**日期：** 2026-05-15  
**范围：** 仅针对 PStab 类型的 datasets 子表；list 子表保持原有 st.data_editor 不变；设计上预留扩展接口。

---

## 决策摘要

| 议题 | 决策 |
|------|------|
| 适用范围 | PStab 表格，预留扩展 |
| 模板存储 | `web/variable_templates.yaml`，Web 端可视化编辑 + 自动保存 |
| 折叠/展开 | 全局按钮 + 每行独立控制 |
| YAML 持久化 | 打平为普通行列表，R 端不变 |
| 加载时链接状态恢复 | 按 Order 推断（Order=0 后紧跟的 Order=1 行视为子行） |

---

## 架构

### 新增文件

```
web/variable_templates.yaml   # 变量类型子行模板
web/templates_io.py           # 模板加载/保存
web/dataset_editor.py         # 卡片式编辑器 Streamlit 组件
```

### 修改文件

```
web/app.py      # Datasets 子表区域调用新编辑器；新增模板管理入口
web/schema.py   # 新增变量类型常量 VAR_TYPES
```

### 不变文件

`yaml_io.py`、`excel_io.py`、所有 R 端代码。新编辑器对外输出仍是相同结构的 flat DataFrame。

---

## 数据模型

### 内部 card state

存于 `st.session_state.datasets_card_state`，结构为 `dict[str, list[dict]]`，每个 dataset 对应一个行列表。

每行字段：

```python
{
    # 数据字段（与 DATASET_TABLE_COLS 一一对应）
    "Class": 1,
    "Label": "年龄（岁）",
    "Order": 0,
    "Aval": "",
    "exclude": 0,
    "BlankCol": "",
    "Drug": "",
    "Visit": "",
    "Base": "",

    # 元数据（仅存在 session_state，不写入 YAML）
    "_id": "uuid-abc",        # 唯一 id，驱动 widget key 稳定性
    "_var_type": "连续变量",  # 变量类型下拉框当前值
    "_parent_id": None,       # None = 父行或独立行
    "_linked": False,         # True = 是子行且仍链接父行（显示 🔗）
    "_expanded": True,        # 父行：是否展开子行
}
```

### 三个关键转换

| 方向 | 逻辑 |
|------|------|
| DataFrame → card state（加载时）| Order=0 开新父组；紧随的 Order=1 行推断为子行，`_linked=True`，`_var_type="手动输入"` |
| card state → DataFrame（保存时）| 按 `(Class, _is_child, Order)` 排序后，过滤 `_*` 字段，打平输出；折叠的子行仍保留在输出中 |
| 变量类型切换时 | 删除该父行所有 `_linked=True` 子行 → 从模板插入新子行（继承父行 Class） |

---

## Class 自动填充逻辑

### 自动填充

- 新增父行（Order=0）：Class = 当前所有父行最大 Class + 1
- 父行展开生成子行时：所有子行 Class 自动继承父行 Class

### 手动修改

- 修改**父行** Class：
  - 若有 `_linked=True` 子行，弹 `st.dialog` 确认：
    - "是" → 所有子行 Class 同步更新
    - "否" → 仅当前行，子行保持原 Class（实际变为独立分组）
  - 修改后按 Class 重排序，rerun

- 修改**子行** Class（仅断链后可编辑）：
  - 自动 `_linked=False`
  - 该子行脱离父组，按新 Class 重排序

### 界面显示

- 父行 Class：正常输入框，可编辑
- 链接子行 Class：`disabled=True`，灰色背景，显示继承值
- 断链子行 Class：正常输入框，白色背景

---

## 变量类型行为

| 类型 | 父行 Aval | 子行生成 |
|------|-----------|----------|
| 连续变量 | 空 | 从模板生成 N 个 Order=1 子行 |
| 分类变量-有子分类 | 空 | 弹 dialog 输入子分类名，每个生成一行 Order=1，Aval="xx (xx.x)" |
| 分类变量-无子分类 | "xx (xx.x)" | 不生成子行 |
| 日期变量 | "YYYY-MM-DD" | 不生成子行（可在模板中配置子行） |
| 手动输入 | 不变 | 不生成子行 |

---

## UI 组件结构

`dataset_editor.py` 导出：
```python
def render_dataset_editor(ds_name: str, card_state: list[dict]) -> list[dict]
```

### 全局控制栏
```
[展开全部]  [折叠全部]  [+ 添加变量行]
```

### 父行卡片
```
▼/▶  [Class: 2 ]  [年龄（岁）___________]  [连续变量 ▼]  [🗑]
```
- Class 输入框宽度固定（约 60px）
- var_type 切换 → 重建子行
- 🗑 删除：若有子行弹确认"是否级联删除子行"

### 子行（父行展开时显示）
```
  🔗  [Class: 2 灰底]  例数              Order:1  Aval: [xx       ]  [断开链接]
  🔗  [Class: 2 灰底]  均值（标准差）    Order:1  Aval: [xx.x (xx)]  [断开链接]
```
- 点"断开链接"：`_linked=False`，Class 变白可编辑
- Label 字段只读（链接状态下）

---

## 模板管理 UI

在 `app.py` 的 `st.expander("变量类型模板配置")` 中：

```
▼ 变量类型模板配置
  连续变量子行：
  │ 例数              xx             [🗑] │
  │ 均值（标准差）    xx.x (xx.xx)   [🗑] │
  │ 中位数            xx.x           [🗑] │
  │ 最小值 - 最大值   xx – xx        [🗑] │
  [+ 添加子行]  [保存模板]

  分类变量-无子分类 Aval：  [xx (xx.x)  ]
  日期变量 Aval：           [YYYY-MM-DD ]
  [保存模板]
```

`templates_io.py` 提供 `load_templates() -> dict` 和 `save_templates(dict)`，直接读写 `web/variable_templates.yaml`，不经过 Git。

---

## variable_templates.yaml 格式

```yaml
连续变量:
  children:
    - {Label: "例数", Aval: "xx"}
    - {Label: "均值（标准差）", Aval: "xx.x (xx.xx)"}
    - {Label: "中位数", Aval: "xx.x"}
    - {Label: "最小值 - 最大值", Aval: "xx – xx"}
分类变量-有子分类:
  children: []
分类变量-无子分类:
  aval: "xx (xx.x)"
日期变量:
  aval: "YYYY-MM-DD"
  children: []
手动输入: {}
```

---

## schema.py 新增常量

```python
VAR_TYPES = [
    "手动输入",
    "连续变量",
    "分类变量-有子分类",
    "分类变量-无子分类",
    "日期变量",
]
VAR_TYPE_DEFAULT = "手动输入"
```

---

## 不受影响的部分

- `yaml_io.py`：dump_yaml / load_yaml 输入输出不变
- `excel_io.py`：不变
- `validators.py`：不变
- R 端所有代码：不变
- list 子表（RptList）：继续使用 `st.data_editor`
