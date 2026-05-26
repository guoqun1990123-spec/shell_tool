# Datasets 卡片式编辑器实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将 Streamlit Datasets 子表从 `st.data_editor` 重构为卡片式编辑器，支持变量类型智能展开、Class 自动填充、父子行联动管理。

**Architecture:** 新增 `dataset_editor.py`（纯 Streamlit 组件）和 `templates_io.py`（模板 IO），`app.py` 调用新组件替换旧 `st.data_editor`；内部状态用 `list[dict]` 存于 `session_state`，保存时打平为 DataFrame，YAML/R 端不变。

**Tech Stack:** Python 3.11+, Streamlit, pandas, PyYAML, uuid

---

## Task 1: schema.py — 新增变量类型常量

**Files:**
- Modify: `web/schema.py`

**Step 1: 在 schema.py 末尾追加常量**

```python
# 变量类型（Datasets 卡片编辑器用）
VAR_TYPES = [
    "手动输入",
    "连续变量",
    "分类变量-有子分类",
    "分类变量-无子分类",
    "日期变量",
]
VAR_TYPE_DEFAULT = "手动输入"
```

**Step 2: 确认不破坏现有导入**

在 `web/` 目录下运行：
```bash
python -c "from schema import VAR_TYPES, VAR_TYPE_DEFAULT; print(VAR_TYPES)"
```
Expected: `['手动输入', '连续变量', '分类变量-有子分类', '分类变量-无子分类', '日期变量']`

**Step 3: Commit**
```bash
git add web/schema.py
git commit -m "feat(web): add VAR_TYPES constants to schema"
```

---

## Task 2: variable_templates.yaml + templates_io.py

**Files:**
- Create: `web/variable_templates.yaml`
- Create: `web/templates_io.py`

**Step 1: 创建 `web/variable_templates.yaml`**

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

**Step 2: 创建 `web/templates_io.py`**

```python
"""变量类型模板的加载/保存，读写 web/variable_templates.yaml。"""
from pathlib import Path
import yaml

_TEMPLATE_FILE = Path(__file__).parent / "variable_templates.yaml"

_DEFAULT: dict = {
    "连续变量": {
        "children": [
            {"Label": "例数", "Aval": "xx"},
            {"Label": "均值（标准差）", "Aval": "xx.x (xx.xx)"},
            {"Label": "中位数", "Aval": "xx.x"},
            {"Label": "最小值 - 最大值", "Aval": "xx – xx"},
        ]
    },
    "分类变量-有子分类": {"children": []},
    "分类变量-无子分类": {"aval": "xx (xx.x)"},
    "日期变量": {"aval": "YYYY-MM-DD", "children": []},
    "手动输入": {},
}


def load_templates() -> dict:
    """加载模板，文件不存在时返回内置默认值。"""
    if not _TEMPLATE_FILE.exists():
        return _DEFAULT
    with open(_TEMPLATE_FILE, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    # 补齐缺失的类型
    for k, v in _DEFAULT.items():
        if k not in data:
            data[k] = v
    return data


def save_templates(templates: dict) -> None:
    """持久化模板到 YAML 文件。"""
    with open(_TEMPLATE_FILE, "w", encoding="utf-8") as f:
        yaml.dump(templates, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
```

**Step 3: 验证 IO**

```bash
python -c "
from templates_io import load_templates, save_templates
t = load_templates()
print(list(t.keys()))
save_templates(t)
print('OK')
"
```
Expected: `['连续变量', '分类变量-有子分类', '分类变量-无子分类', '日期变量', '手动输入']` 然后 `OK`

**Step 4: Commit**
```bash
git add web/variable_templates.yaml web/templates_io.py
git commit -m "feat(web): add variable_templates.yaml and templates_io"
```

---

## Task 3: dataset_editor.py — 状态转换纯函数

这是最重要的一步。先写纯函数，后续 UI 层调用它们。

**Files:**
- Create: `web/dataset_editor.py`
- Create: `web/tests/test_dataset_editor.py`

**Step 1: 创建测试文件 `web/tests/test_dataset_editor.py`**

```python
"""纯函数单元测试（不依赖 Streamlit）。"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd
import pytest
from dataset_editor import df_to_card_state, card_state_to_df, get_next_class


# ── df_to_card_state ────────────────────────────────────────────────────────

def test_df_to_card_state_empty():
    df = pd.DataFrame(columns=["Class","Label","Order","Aval","exclude","BlankCol","Drug","Visit","Base"])
    result = df_to_card_state(df)
    assert result == []


def test_df_to_card_state_flat_rows():
    """两个独立 Order=0 行，无子行。"""
    df = pd.DataFrame([
        {"Class": 1, "Label": "年龄", "Order": 0, "Aval": "", "exclude": 0, "BlankCol": "", "Drug": "", "Visit": "", "Base": ""},
        {"Class": 2, "Label": "性别", "Order": 0, "Aval": "", "exclude": 0, "BlankCol": "", "Drug": "", "Visit": "", "Base": ""},
    ])
    result = df_to_card_state(df)
    assert len(result) == 2
    assert all(r["_parent_id"] is None for r in result)
    assert all(r["_linked"] is False for r in result)
    assert all(r["_var_type"] == "手动输入" for r in result)


def test_df_to_card_state_infers_children():
    """Order=0 后跟 Order=1 行，应被推断为子行。"""
    df = pd.DataFrame([
        {"Class": 1, "Label": "年龄", "Order": 0, "Aval": "", "exclude": 0, "BlankCol": "", "Drug": "", "Visit": "", "Base": ""},
        {"Class": 1, "Label": "例数", "Order": 1, "Aval": "xx", "exclude": 0, "BlankCol": "", "Drug": "", "Visit": "", "Base": ""},
        {"Class": 1, "Label": "均值", "Order": 1, "Aval": "xx.x", "exclude": 0, "BlankCol": "", "Drug": "", "Visit": "", "Base": ""},
    ])
    result = df_to_card_state(df)
    assert len(result) == 3
    parent = result[0]
    child1, child2 = result[1], result[2]
    assert parent["_parent_id"] is None
    assert child1["_parent_id"] == parent["_id"]
    assert child2["_parent_id"] == parent["_id"]
    assert child1["_linked"] is True
    assert child2["_linked"] is True


# ── card_state_to_df ────────────────────────────────────────────────────────

def test_card_state_to_df_strips_meta():
    """输出 DataFrame 不含 _ 前缀字段。"""
    state = [
        {"Class": 1, "Label": "年龄", "Order": 0, "Aval": "", "exclude": 0,
         "BlankCol": "", "Drug": "", "Visit": "", "Base": "",
         "_id": "x1", "_var_type": "连续变量", "_parent_id": None,
         "_linked": False, "_expanded": True},
    ]
    df = card_state_to_df(state)
    assert "_id" not in df.columns
    assert "_var_type" not in df.columns
    assert "Label" in df.columns


def test_card_state_to_df_preserves_collapsed_children():
    """折叠状态的子行仍要写入 DataFrame。"""
    state = [
        {"Class": 1, "Label": "年龄", "Order": 0, "Aval": "", "exclude": 0,
         "BlankCol": "", "Drug": "", "Visit": "", "Base": "",
         "_id": "p1", "_var_type": "连续变量", "_parent_id": None,
         "_linked": False, "_expanded": False},
        {"Class": 1, "Label": "例数", "Order": 1, "Aval": "xx", "exclude": 0,
         "BlankCol": "", "Drug": "", "Visit": "", "Base": "",
         "_id": "c1", "_var_type": "手动输入", "_parent_id": "p1",
         "_linked": True, "_expanded": False},
    ]
    df = card_state_to_df(state)
    assert len(df) == 2


# ── get_next_class ──────────────────────────────────────────────────────────

def test_get_next_class_empty():
    assert get_next_class([]) == 1


def test_get_next_class_increments():
    state = [
        {"Class": 1, "_parent_id": None},
        {"Class": 2, "_parent_id": None},
        {"Class": 3, "_parent_id": None},
    ]
    assert get_next_class(state) == 4


def test_get_next_class_ignores_children():
    """子行 Class 不参与计算。"""
    state = [
        {"Class": 1, "_parent_id": None},
        {"Class": 1, "_parent_id": "p1"},  # child
        {"Class": 5, "_parent_id": "p1"},  # child with higher Class — ignored
    ]
    assert get_next_class(state) == 2
```

**Step 2: 运行测试，确认全部 FAIL（模块不存在）**

```bash
cd web && python -m pytest tests/test_dataset_editor.py -v 2>&1 | head -20
```
Expected: `ModuleNotFoundError: No module named 'dataset_editor'`

**Step 3: 创建 `web/dataset_editor.py`，先只写纯函数**

```python
"""卡片式 Datasets 编辑器。

公开接口：
  df_to_card_state(df)          DataFrame → list[dict]（含 _* 元数据）
  card_state_to_df(state)       list[dict] → DataFrame（去除 _* 元数据）
  get_next_class(state)         计算新父行应得的 Class 值
  render_dataset_editor(...)    Streamlit UI 组件（Task 4 实现）
"""
import uuid
import pandas as pd

from schema import DATASET_TABLE_COLS, VAR_TYPE_DEFAULT

# ── 元数据键（不写入 YAML）──────────────────────────────────────────────────
_META_KEYS = {"_id", "_var_type", "_parent_id", "_linked", "_expanded"}


def _new_meta(
    var_type: str = VAR_TYPE_DEFAULT,
    parent_id: str | None = None,
    linked: bool = False,
    expanded: bool = True,
) -> dict:
    return {
        "_id": str(uuid.uuid4()),
        "_var_type": var_type,
        "_parent_id": parent_id,
        "_linked": linked,
        "_expanded": expanded,
    }


def _row_data(row: dict) -> dict:
    """提取数据字段（去除 _* 元数据）。"""
    return {k: v for k, v in row.items() if k not in _META_KEYS}


# ── 纯函数 ─────────────────────────────────────────────────────────────────

def df_to_card_state(df: pd.DataFrame) -> list[dict]:
    """
    DataFrame → card state。
    推断规则：Order=0 行为父行；其后紧随的 Order=1 行为子行（_linked=True）。
    """
    if df is None or df.empty:
        return []

    records = df.to_dict(orient="records")
    result: list[dict] = []
    current_parent_id: str | None = None

    for rec in records:
        order = int(rec.get("Order") or 0)
        data = {col: rec.get(col, "") for col in DATASET_TABLE_COLS}
        # 修正数值类型
        data["Order"] = order
        data["exclude"] = int(rec.get("exclude") or 0)
        # 尝试将 Class 转为 int
        try:
            data["Class"] = int(rec.get("Class") or 0)
        except (ValueError, TypeError):
            data["Class"] = 0

        if order == 0:
            meta = _new_meta(var_type=VAR_TYPE_DEFAULT, parent_id=None, linked=False)
            current_parent_id = meta["_id"]
        else:
            meta = _new_meta(var_type=VAR_TYPE_DEFAULT, parent_id=current_parent_id, linked=True)

        result.append({**data, **meta})

    return result


def card_state_to_df(state: list[dict]) -> pd.DataFrame:
    """
    card state → DataFrame。
    按 (Class, _is_child, Order) 排序后，去除 _* 字段，打平输出。
    折叠状态子行仍保留。
    """
    if not state:
        return pd.DataFrame(columns=DATASET_TABLE_COLS)

    def sort_key(r):
        cls = int(r.get("Class") or 0)
        is_child = 1 if r.get("_parent_id") else 0
        order = int(r.get("Order") or 0)
        return (cls, is_child, order)

    sorted_state = sorted(state, key=sort_key)
    rows = [_row_data(r) for r in sorted_state]
    df = pd.DataFrame(rows, columns=DATASET_TABLE_COLS)
    # 确保数值列类型
    df["Order"] = pd.to_numeric(df["Order"], errors="coerce").fillna(0).astype(int)
    df["exclude"] = pd.to_numeric(df["exclude"], errors="coerce").fillna(0).astype(int)
    return df


def get_next_class(state: list[dict]) -> int:
    """计算新父行应得的 Class（当前所有父行最大 Class + 1）。"""
    parent_classes = [
        int(r.get("Class") or 0)
        for r in state
        if r.get("_parent_id") is None
    ]
    return max(parent_classes, default=0) + 1
```

**Step 4: 运行测试，应全部通过**

```bash
cd web && python -m pytest tests/test_dataset_editor.py -v
```
Expected: 全部 PASS

**Step 5: Commit**
```bash
git add web/dataset_editor.py web/tests/test_dataset_editor.py
git commit -m "feat(web): add card state pure functions with tests"
```

---

## Task 4: dataset_editor.py — 状态操作函数

添加行级操作的纯/半纯函数（不含 Streamlit 渲染，但用于操作 card state）。

**Files:**
- Modify: `web/dataset_editor.py`（追加函数）
- Modify: `web/tests/test_dataset_editor.py`（追加测试）

**Step 1: 在测试文件末尾追加**

```python
# ── 状态操作函数 ─────────────────────────────────────────────────────────────

from dataset_editor import (
    add_parent_row, delete_row, expand_var_type,
    unlink_child, sync_children_class,
)
from unittest.mock import patch


def _make_templates():
    return {
        "连续变量": {
            "children": [
                {"Label": "例数", "Aval": "xx"},
                {"Label": "均值（标准差）", "Aval": "xx.x (xx.xx)"},
            ]
        },
        "分类变量-无子分类": {"aval": "xx (xx.x)"},
        "手动输入": {},
    }


def test_add_parent_row_gets_next_class():
    state = [{"Class": 2, "_parent_id": None, "_id": "p1", "_var_type": "手动输入",
              "_linked": False, "_expanded": True,
              "Label": "X", "Order": 0, "Aval": "", "exclude": 0, "BlankCol": "", "Drug": "", "Visit": "", "Base": ""}]
    new_state = add_parent_row(state)
    new_row = new_state[-1]
    assert new_row["Class"] == 3
    assert new_row["Order"] == 0
    assert new_row["_parent_id"] is None


def test_delete_parent_cascades_children():
    state = [
        {"_id": "p1", "_parent_id": None, "Class": 1, "Order": 0, "Label": "A",
         "Aval": "", "exclude": 0, "BlankCol": "", "Drug": "", "Visit": "", "Base": "",
         "_var_type": "连续变量", "_linked": False, "_expanded": True},
        {"_id": "c1", "_parent_id": "p1", "Class": 1, "Order": 1, "Label": "例数",
         "Aval": "xx", "exclude": 0, "BlankCol": "", "Drug": "", "Visit": "", "Base": "",
         "_var_type": "手动输入", "_linked": True, "_expanded": True},
    ]
    new_state = delete_row(state, "p1", cascade=True)
    assert len(new_state) == 0


def test_delete_parent_no_cascade():
    state = [
        {"_id": "p1", "_parent_id": None, "Class": 1, "Order": 0, "Label": "A",
         "Aval": "", "exclude": 0, "BlankCol": "", "Drug": "", "Visit": "", "Base": "",
         "_var_type": "连续变量", "_linked": False, "_expanded": True},
        {"_id": "c1", "_parent_id": "p1", "Class": 1, "Order": 1, "Label": "例数",
         "Aval": "xx", "exclude": 0, "BlankCol": "", "Drug": "", "Visit": "", "Base": "",
         "_var_type": "手动输入", "_linked": True, "_expanded": True},
    ]
    new_state = delete_row(state, "p1", cascade=False)
    # 子行 parent_id 应置 None（变为独立行）
    assert len(new_state) == 1
    assert new_state[0]["_parent_id"] is None


def test_expand_var_type_continuous():
    state = [
        {"_id": "p1", "_parent_id": None, "Class": 1, "Order": 0, "Label": "年龄",
         "Aval": "", "exclude": 0, "BlankCol": "", "Drug": "", "Visit": "", "Base": "",
         "_var_type": "手动输入", "_linked": False, "_expanded": True},
    ]
    templates = _make_templates()
    new_state = expand_var_type(state, "p1", "连续变量", templates)
    parent = next(r for r in new_state if r["_id"] == "p1")
    children = [r for r in new_state if r["_parent_id"] == "p1"]
    assert parent["_var_type"] == "连续变量"
    assert len(children) == 2
    assert all(c["_linked"] for c in children)
    assert all(c["Class"] == 1 for c in children)


def test_unlink_child():
    state = [
        {"_id": "p1", "_parent_id": None, "Class": 1, "Order": 0, "Label": "A",
         "Aval": "", "exclude": 0, "BlankCol": "", "Drug": "", "Visit": "", "Base": "",
         "_var_type": "连续变量", "_linked": False, "_expanded": True},
        {"_id": "c1", "_parent_id": "p1", "Class": 1, "Order": 1, "Label": "例数",
         "Aval": "xx", "exclude": 0, "BlankCol": "", "Drug": "", "Visit": "", "Base": "",
         "_var_type": "手动输入", "_linked": True, "_expanded": True},
    ]
    new_state = unlink_child(state, "c1")
    child = next(r for r in new_state if r["_id"] == "c1")
    assert child["_linked"] is False


def test_sync_children_class():
    state = [
        {"_id": "p1", "_parent_id": None, "Class": 1, "Order": 0, "Label": "A",
         "Aval": "", "exclude": 0, "BlankCol": "", "Drug": "", "Visit": "", "Base": "",
         "_var_type": "连续变量", "_linked": False, "_expanded": True},
        {"_id": "c1", "_parent_id": "p1", "Class": 1, "Order": 1, "Label": "例数",
         "Aval": "xx", "exclude": 0, "BlankCol": "", "Drug": "", "Visit": "", "Base": "",
         "_var_type": "手动输入", "_linked": True, "_expanded": True},
    ]
    new_state = sync_children_class(state, "p1", new_class=5)
    parent = next(r for r in new_state if r["_id"] == "p1")
    child = next(r for r in new_state if r["_id"] == "c1")
    assert parent["Class"] == 5
    assert child["Class"] == 5
```

**Step 2: 运行测试，确认 FAIL（函数未实现）**

```bash
cd web && python -m pytest tests/test_dataset_editor.py -v -k "add_parent or delete or expand or unlink or sync" 2>&1 | tail -5
```

**Step 3: 在 `web/dataset_editor.py` 中追加操作函数**

追加到文件末尾（`render_dataset_editor` 占位函数之前）：

```python
# ── 状态操作函数 ────────────────────────────────────────────────────────────

def _new_data_row(class_val: int = 0, order: int = 0) -> dict:
    return {col: "" for col in DATASET_TABLE_COLS} | {"Class": class_val, "Order": order, "exclude": 0}


def add_parent_row(state: list[dict]) -> list[dict]:
    """在末尾追加一个新父行，Class = max父行Class + 1。"""
    cls = get_next_class(state)
    row = _new_data_row(class_val=cls, order=0) | _new_meta()
    return state + [row]


def delete_row(state: list[dict], row_id: str, cascade: bool) -> list[dict]:
    """
    删除指定行。
    cascade=True：同时删除所有 _linked=True 且 _parent_id==row_id 的子行。
    cascade=False：子行 _parent_id 置 None，变为独立行。
    """
    new_state = []
    for r in state:
        if r["_id"] == row_id:
            continue
        if r.get("_parent_id") == row_id:
            if cascade:
                continue
            else:
                r = {**r, "_parent_id": None, "_linked": False}
        new_state.append(r)
    return new_state


def expand_var_type(
    state: list[dict],
    parent_id: str,
    new_var_type: str,
    templates: dict,
) -> list[dict]:
    """
    切换父行变量类型：
    1. 删除该父行的所有 _linked 子行
    2. 按模板插入新子行（继承父行 Class）
    3. 更新父行 _var_type 和 Aval
    """
    # 找父行
    parent = next((r for r in state if r["_id"] == parent_id), None)
    if parent is None:
        return state

    cls = parent.get("Class", 0)
    tmpl = templates.get(new_var_type, {})

    # 删除旧链接子行
    new_state = [r for r in state if not (r.get("_parent_id") == parent_id and r.get("_linked"))]

    # 更新父行
    new_state = [
        {**r, "_var_type": new_var_type, "Aval": tmpl.get("aval", r.get("Aval", ""))}
        if r["_id"] == parent_id else r
        for r in new_state
    ]

    # 找父行在新列表中的位置，插入子行
    parent_idx = next(i for i, r in enumerate(new_state) if r["_id"] == parent_id)
    children = []
    for child_tmpl in tmpl.get("children", []):
        child_data = _new_data_row(class_val=cls, order=1) | child_tmpl
        child_meta = _new_meta(parent_id=parent_id, linked=True)
        children.append({**child_data, **child_meta})

    return new_state[:parent_idx + 1] + children + new_state[parent_idx + 1:]


def unlink_child(state: list[dict], child_id: str) -> list[dict]:
    """断开子行链接，使其变为可独立编辑的行。"""
    return [
        {**r, "_linked": False, "_parent_id": None} if r["_id"] == child_id else r
        for r in state
    ]


def sync_children_class(state: list[dict], parent_id: str, new_class: int) -> list[dict]:
    """将父行及其所有 _linked 子行的 Class 同步为 new_class。"""
    return [
        {**r, "Class": new_class}
        if r["_id"] == parent_id or (r.get("_parent_id") == parent_id and r.get("_linked"))
        else r
        for r in state
    ]
```

**Step 4: 运行全部测试**

```bash
cd web && python -m pytest tests/test_dataset_editor.py -v
```
Expected: 全部 PASS

**Step 5: Commit**
```bash
git add web/dataset_editor.py web/tests/test_dataset_editor.py
git commit -m "feat(web): add card state mutation functions with tests"
```

---

## Task 5: dataset_editor.py — render_dataset_editor() UI

实现 Streamlit 渲染函数。此函数有副作用（写 session_state），不写单元测试，靠手动验证。

**Files:**
- Modify: `web/dataset_editor.py`（追加/替换 render_dataset_editor）

**Step 1: 在 `web/dataset_editor.py` 末尾追加 render 函数**

```python
# ── Streamlit UI ────────────────────────────────────────────────────────────

def _state_key(ds_name: str) -> str:
    return f"card_state_{ds_name}"


def _ensure_card_state(ds_name: str, df: pd.DataFrame) -> list[dict]:
    """确保 session_state 中有该 dataset 的 card state，不存在则从 df 初始化。"""
    import streamlit as st
    key = _state_key(ds_name)
    if key not in st.session_state:
        st.session_state[key] = df_to_card_state(df)
    return st.session_state[key]


def render_dataset_editor(ds_name: str, df: pd.DataFrame, templates: dict) -> pd.DataFrame:
    """
    渲染卡片式编辑器，返回当前编辑结果（DataFrame）。
    调用方负责将返回值写回 session_state.datasets[ds_name]。
    """
    import streamlit as st

    state = _ensure_card_state(ds_name, df)
    key = _state_key(ds_name)

    # ── 全局控制栏 ────────────────────────────────────────────────────────
    col_exp, col_col, col_add = st.columns([1, 1, 2])
    with col_exp:
        if st.button("展开全部", key=f"{ds_name}_expand_all"):
            state = [{**r, "_expanded": True} for r in state]
            st.session_state[key] = state
    with col_col:
        if st.button("折叠全部", key=f"{ds_name}_collapse_all"):
            state = [{**r, "_expanded": True} for r in state]  # 折叠：子行仍存在，父行标记
            state = [{**r, "_expanded": False} for r in state if r["_parent_id"] is None] + \
                    [r for r in state if r["_parent_id"] is not None]
            # 重建：父行 _expanded=False
            state = [
                {**r, "_expanded": False} if r["_parent_id"] is None else r
                for r in st.session_state[key]
            ]
            st.session_state[key] = state
    with col_add:
        if st.button("＋ 添加变量行", key=f"{ds_name}_add_row", type="secondary"):
            st.session_state[key] = add_parent_row(st.session_state[key])
            st.rerun()

    state = st.session_state[key]

    # ── 行渲染 ────────────────────────────────────────────────────────────
    from schema import VAR_TYPES
    changed = False

    for i, row in enumerate(state):
        if row.get("_parent_id") is not None:
            continue  # 子行在父行处理中渲染

        row_id = row["_id"]
        is_expanded = row.get("_expanded", True)
        children = [r for r in state if r.get("_parent_id") == row_id and r.get("_linked")]

        # 父行卡片
        with st.container(border=True):
            c_toggle, c_class, c_label, c_type, c_del = st.columns([0.5, 1, 4, 2, 0.5])

            with c_toggle:
                toggle_label = "▼" if is_expanded else "▶"
                if st.button(toggle_label, key=f"toggle_{row_id}"):
                    state = [{**r, "_expanded": not r["_expanded"]} if r["_id"] == row_id else r for r in state]
                    st.session_state[key] = state
                    st.rerun()

            with c_class:
                new_class = st.number_input(
                    "Class", value=int(row.get("Class") or 0),
                    step=1, min_value=0, label_visibility="collapsed",
                    key=f"class_{row_id}"
                )
                if new_class != int(row.get("Class") or 0):
                    if children:
                        st.session_state[f"pending_class_{row_id}"] = new_class
                    else:
                        state = [{**r, "Class": new_class} if r["_id"] == row_id else r for r in state]
                        st.session_state[key] = state
                        changed = True

            with c_label:
                new_label = st.text_input(
                    "Label", value=str(row.get("Label") or ""),
                    placeholder="变量名称", label_visibility="collapsed",
                    key=f"label_{row_id}"
                )
                if new_label != str(row.get("Label") or ""):
                    state = [{**r, "Label": new_label} if r["_id"] == row_id else r for r in state]
                    st.session_state[key] = state
                    changed = True

            with c_type:
                cur_type = row.get("_var_type", "手动输入")
                new_type = st.selectbox(
                    "类型", options=VAR_TYPES,
                    index=VAR_TYPES.index(cur_type) if cur_type in VAR_TYPES else 0,
                    label_visibility="collapsed",
                    key=f"vartype_{row_id}"
                )
                if new_type != cur_type:
                    state = expand_var_type(state, row_id, new_type, templates)
                    st.session_state[key] = state
                    st.rerun()

            with c_del:
                if st.button("🗑", key=f"del_{row_id}"):
                    if children:
                        st.session_state[f"confirm_del_{row_id}"] = True
                    else:
                        st.session_state[key] = delete_row(state, row_id, cascade=True)
                        st.rerun()

        # Class 修改确认对话框
        pending_class_key = f"pending_class_{row_id}"
        if pending_class_key in st.session_state:
            new_cls = st.session_state[pending_class_key]
            st.warning(f"是否同步修改 Class={row.get('Class')} → {new_cls} 到所有子行？")
            col_y, col_n = st.columns(2)
            with col_y:
                if st.button("是，同步子行", key=f"cls_yes_{row_id}"):
                    state = sync_children_class(state, row_id, new_cls)
                    st.session_state[key] = state
                    del st.session_state[pending_class_key]
                    st.rerun()
            with col_n:
                if st.button("否，仅当前行", key=f"cls_no_{row_id}"):
                    state = [{**r, "Class": new_cls} if r["_id"] == row_id else r for r in state]
                    st.session_state[key] = state
                    del st.session_state[pending_class_key]
                    st.rerun()

        # 删除确认
        confirm_del_key = f"confirm_del_{row_id}"
        if confirm_del_key in st.session_state:
            st.warning(f"变量「{row.get('Label')}」有 {len(children)} 个子行，是否一并删除？")
            col_y, col_n = st.columns(2)
            with col_y:
                if st.button("是，级联删除", key=f"del_yes_{row_id}"):
                    st.session_state[key] = delete_row(state, row_id, cascade=True)
                    del st.session_state[confirm_del_key]
                    st.rerun()
            with col_n:
                if st.button("否，保留子行", key=f"del_no_{row_id}"):
                    st.session_state[key] = delete_row(state, row_id, cascade=False)
                    del st.session_state[confirm_del_key]
                    st.rerun()

        # 子行渲染（仅展开时）
        if is_expanded:
            for child in children:
                child_id = child["_id"]
                with st.container():
                    cc_link, cc_class, cc_label, cc_aval, cc_unlink = st.columns([0.5, 1, 3, 3, 1.5])
                    with cc_link:
                        st.markdown("🔗")
                    with cc_class:
                        # 子行 Class：灰色禁用显示
                        st.text_input(
                            "Class", value=str(child.get("Class") or ""),
                            disabled=True, label_visibility="collapsed",
                            key=f"child_class_{child_id}"
                        )
                    with cc_label:
                        st.text_input(
                            "Label", value=str(child.get("Label") or ""),
                            disabled=True, label_visibility="collapsed",
                            key=f"child_label_{child_id}"
                        )
                    with cc_aval:
                        new_aval = st.text_input(
                            "Aval", value=str(child.get("Aval") or ""),
                            label_visibility="collapsed",
                            key=f"child_aval_{child_id}"
                        )
                        if new_aval != str(child.get("Aval") or ""):
                            state = [{**r, "Aval": new_aval} if r["_id"] == child_id else r for r in state]
                            st.session_state[key] = state
                            changed = True
                    with cc_unlink:
                        if st.button("断开链接", key=f"unlink_{child_id}"):
                            st.session_state[key] = unlink_child(state, child_id)
                            st.rerun()

    # 渲染断链的独立子行（_parent_id=None 但 Order=1）
    for row in state:
        if row.get("_parent_id") is not None:
            continue
        if int(row.get("Order") or 0) != 1:
            continue
        # 断链的子行：普通父行方式渲染（已在上方循环中处理，Order=0 才进入）
        # Order=1 的断链行作为普通行展示
        row_id = row["_id"]
        with st.container(border=True):
            cc, cl, ca, cd = st.columns([1, 3, 3, 0.5])
            with cc:
                new_class = st.number_input(
                    "Class", value=int(row.get("Class") or 0),
                    step=1, min_value=0, label_visibility="collapsed",
                    key=f"unlinked_class_{row_id}"
                )
                if new_class != int(row.get("Class") or 0):
                    state = [{**r, "Class": new_class} if r["_id"] == row_id else r for r in state]
                    st.session_state[key] = state
                    changed = True
            with cl:
                new_label = st.text_input(
                    "Label", value=str(row.get("Label") or ""),
                    label_visibility="collapsed", key=f"unlinked_label_{row_id}"
                )
                if new_label != str(row.get("Label") or ""):
                    state = [{**r, "Label": new_label} if r["_id"] == row_id else r for r in state]
                    st.session_state[key] = state
                    changed = True
            with ca:
                new_aval = st.text_input(
                    "Aval", value=str(row.get("Aval") or ""),
                    label_visibility="collapsed", key=f"unlinked_aval_{row_id}"
                )
                if new_aval != str(row.get("Aval") or ""):
                    state = [{**r, "Aval": new_aval} if r["_id"] == row_id else r for r in state]
                    st.session_state[key] = state
                    changed = True
            with cd:
                if st.button("🗑", key=f"del_unlinked_{row_id}"):
                    st.session_state[key] = delete_row(state, row_id, cascade=False)
                    st.rerun()

    return card_state_to_df(st.session_state[key])
```

**Step 2: 语法检查**

```bash
cd web && python -c "import dataset_editor; print('OK')"
```
Expected: `OK`

**Step 3: Commit**
```bash
git add web/dataset_editor.py
git commit -m "feat(web): implement render_dataset_editor Streamlit component"
```

---

## Task 6: app.py — 集成卡片编辑器（替换 PStab data_editor）

**Files:**
- Modify: `web/app.py`

**Step 1: 在 `app.py` 顶部 import 块中添加**

在 `from validators import validate` 之后追加：
```python
from dataset_editor import render_dataset_editor, df_to_card_state, card_state_to_df, _state_key
from templates_io import load_templates
```

**Step 2: 替换 Datasets 子表渲染逻辑**

定位 `app.py` 第 264–278 行（`if ds_name and ds_name in st.session_state.datasets:` 块），将整个 `if/elif/else` 块替换为：

```python
        if ds_name and ds_name in st.session_state.datasets:
            is_list = ds_name == "list"
            ds_df = st.session_state.datasets[ds_name]

            if is_list:
                # list 子表保持原 data_editor
                ds_cc = _build_dataset_column_config(is_list=True)
                edited_ds = st.data_editor(
                    ds_df,
                    column_config=ds_cc,
                    num_rows="dynamic",
                    width="stretch",
                    key=f"ds_editor_{ds_name}_{st.session_state.editor_version}",
                )
                st.session_state.datasets[ds_name] = edited_ds
            else:
                # PStab 表格：卡片编辑器
                # 加载/新建时同步重置 card state
                card_key = _state_key(ds_name)
                if f"_ds_version_{ds_name}" not in st.session_state or \
                        st.session_state[f"_ds_version_{ds_name}"] != st.session_state.editor_version:
                    st.session_state[card_key] = df_to_card_state(ds_df)
                    st.session_state[f"_ds_version_{ds_name}"] = st.session_state.editor_version

                templates = load_templates()
                result_df = render_dataset_editor(ds_name, ds_df, templates)
                st.session_state.datasets[ds_name] = result_df

        elif ds_name:
            st.info(f"数据表 '{ds_name}' 尚未创建，请在上方新建。")
        else:
            st.info("当前行未填写 Datasets 字段，或 MacVar=mtext 不需要数据表。")
```

**Step 3: 确认 `_do_save` 中 `dump_yaml` 调用无需修改**

`dump_yaml` 接收 `st.session_state.datasets`（值已是 DataFrame），Task 5 中 `render_dataset_editor` 返回值已写回，无需额外处理。

**Step 4: 语法检查**

```bash
cd web && python -c "import ast; ast.parse(open('app.py').read()); print('syntax OK')"
```
Expected: `syntax OK`

**Step 5: Commit**
```bash
git add web/app.py
git commit -m "feat(web): integrate card editor into app, keep list editor unchanged"
```

---

## Task 7: app.py — 模板管理 UI

**Files:**
- Modify: `web/app.py`（在 Datasets 子表区域下方新增 expander）

**Step 1: 在 `app.py` 的 `st.divider()` 前（状态栏之前）添加模板 expander**

定位 `# ── 状态栏 + 保存按钮` 注释前的 `st.divider()`，在其**之前**插入：

```python
    # ── 模板管理 ────────────────────────────────────────────────────────────
    with st.expander("变量类型模板配置"):
        from templates_io import save_templates
        templates_edit = load_templates()

        st.caption("连续变量子行（Label + Aval 模板）")
        cont_children = templates_edit.get("连续变量", {}).get("children", [])
        new_children = []
        for j, child in enumerate(cont_children):
            c1, c2, c3 = st.columns([3, 3, 0.5])
            with c1:
                lbl = st.text_input("Label", value=child.get("Label", ""),
                                    label_visibility="collapsed",
                                    key=f"tmpl_label_{j}")
            with c2:
                avl = st.text_input("Aval", value=child.get("Aval", ""),
                                    label_visibility="collapsed",
                                    key=f"tmpl_aval_{j}")
            with c3:
                if not st.button("🗑", key=f"tmpl_del_{j}"):
                    new_children.append({"Label": lbl, "Aval": avl})
        if st.button("＋ 添加子行", key="tmpl_add"):
            new_children.append({"Label": "", "Aval": ""})
        templates_edit["连续变量"]["children"] = new_children

        col_a, col_b = st.columns(2)
        with col_a:
            st.caption("分类变量-无子分类 Aval")
            templates_edit["分类变量-无子分类"]["aval"] = st.text_input(
                "Aval", value=templates_edit.get("分类变量-无子分类", {}).get("aval", "xx (xx.x)"),
                key="tmpl_cat_aval", label_visibility="collapsed"
            )
        with col_b:
            st.caption("日期变量 Aval")
            templates_edit["日期变量"]["aval"] = st.text_input(
                "Aval", value=templates_edit.get("日期变量", {}).get("aval", "YYYY-MM-DD"),
                key="tmpl_date_aval", label_visibility="collapsed"
            )

        if st.button("保存模板", key="btn_save_tmpl", type="secondary"):
            save_templates(templates_edit)
            st.success("模板已保存")
```

**Step 2: 语法检查**

```bash
cd web && python -c "import ast; ast.parse(open('app.py').read()); print('syntax OK')"
```

**Step 3: Commit**
```bash
git add web/app.py
git commit -m "feat(web): add variable template management UI"
```

---

## Task 8: 手动集成验证

启动 Streamlit 并验证以下场景：

```bash
cd web && streamlit run app.py
```

**验证清单：**

1. **加载 YAML 文件** → Datasets 子表显示卡片（非 data_editor），行数与 YAML 一致
2. **添加变量行** → Class 自动为 max+1
3. **切换为"连续变量"** → 自动插入 4 个子行，Class 继承父行
4. **折叠父行** → 子行隐藏；点展开恢复
5. **全局展开/折叠** → 所有父行同步
6. **修改父行 Class（有子行）** → 弹出确认框；选"是"子行同步；选"否"仅父行变
7. **断开子行链接** → 🔗 消失，Class 变白色可编辑
8. **删除父行（有子行）** → 弹出确认；级联删除
9. **list 子表（RptList 类型）** → 仍显示 data_editor，不受影响
10. **保存并提交 Git** → YAML 结构无变化（flat 行列表），R 端可正常解析

**Step 2: 运行全部单元测试**

```bash
cd web && python -m pytest tests/test_dataset_editor.py -v
```
Expected: 全部 PASS

**Step 3: Final commit（如有遗漏修改）**

```bash
git add -A
git commit -m "feat(web): datasets card editor complete"
```
