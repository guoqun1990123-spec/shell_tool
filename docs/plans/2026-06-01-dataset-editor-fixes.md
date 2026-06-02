# Dataset Editor Fixes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 修复 Datasets 编辑器中 10 个已识别问题，涵盖 Class 编号逻辑、导出排序、断链行处理、性能优化和行为一致性。

**Architecture:** 所有修改集中在 `web/dataset_editor.py` 和 `R/generators/generate_table.R`，外科手术式逐点修改。Python 侧改 Class 生成逻辑、导出顺序、断链行过滤；R 侧改标题行的空行插入策略。无新文件，无新抽象。

**Tech Stack:** Python 3, Streamlit, pandas, R (flextable/officer)

---

## 背景知识（实现者必读）

### Class 在 R 端的唯一用途

`R/generators/generate_table.R` 的 `build_table_data` 函数遍历 DataFrame，检测相邻行 `Class` 值变化时插入分隔空行：

```r
if (!is.na(prev_class) && !is.na(current_class) && prev_class != current_class) {
  # 插空行
}
prev_class <- current_class
```

**Class 值本身无意义，只有「相邻行是否相等」决定分组边界。**

### 修复后 Class 约定

- **标题行**（`_is_header=True`）：`Class=0`，固定，不参与编号分配
- **数据变量行**：按 UI 中出现顺序从 1 递增
- **同一变量的父行+子行**：同一 Class

### R 端标题行渲染策略（修复后）

标题行 `Class=0`，R 端遇到 `Class=0` 的行时：不插前置空行，直接渲染为加粗标题行（即标题行前只有上一组变化触发的空行，标题行后不额外空行）。

---

## Task 1：`_reindex_class` 跳过标题行，标题行 Class 固定 0

**Files:**
- Modify: `web/dataset_editor.py`

**当前代码**（约第 440-457 行）：

```python
def _reindex_class(state: list[dict]) -> list[dict]:
    parents = _parent_order(state)
    class_map: dict[str, int] = {p["_id"]: i + 1 for i, p in enumerate(parents)}
    result = []
    for r in state:
        rid = r["_id"]
        pid = r.get("_parent_id")
        if rid in class_map:
            result.append({**r, "Class": class_map[rid]})
        elif pid in class_map and r.get("_linked"):
            result.append({**r, "Class": class_map[pid]})
        else:
            result.append(r)
    return result
```

`_parent_order`（约第 432-437 行）：

```python
def _parent_order(state: list[dict]) -> list[dict]:
    return [r for r in state if r.get("_parent_id") is None and int(r.get("Order") or 0) == 0]
```

**Step 1: 修改 `_parent_order`，过滤掉标题行**

```python
def _parent_order(state: list[dict]) -> list[dict]:
    """返回所有 Order=0 非标题父行，按当前在 state 中的出现顺序。"""
    return [r for r in state
            if r.get("_parent_id") is None
            and int(r.get("Order") or 0) == 0
            and not r.get("_is_header")]
```

**Step 2: 修改 `_reindex_class`，标题行 Class 强制置 0**

```python
def _reindex_class(state: list[dict]) -> list[dict]:
    """
    按非标题父行在 state 中的顺序重新分配 Class（从 1 递增）。
    标题行 Class 固定为 0，不参与编号分配。
    同步更新每个父行的 linked 子行 Class，断链行 Class 不变。
    """
    parents = _parent_order(state)
    class_map: dict[str, int] = {p["_id"]: i + 1 for i, p in enumerate(parents)}
    result = []
    for r in state:
        if r.get("_is_header"):
            result.append({**r, "Class": 0})
        elif r["_id"] in class_map:
            result.append({**r, "Class": class_map[r["_id"]]})
        elif r.get("_parent_id") in class_map and r.get("_linked"):
            result.append({**r, "Class": class_map[r.get("_parent_id")]})
        else:
            result.append(r)
    return result
```

**Step 3: Commit**

```bash
cd d:/shell_tool
git add web/dataset_editor.py
git commit -m "fix: _reindex_class 跳过标题行，标题行 Class 固定为 0"
```

---

## Task 2：`get_next_class` 跳过标题行

**Files:**
- Modify: `web/dataset_editor.py`

**当前代码**（约第 118-127 行）：

```python
def get_next_class(state: list[dict]) -> int:
    """计算新父行应得的 Class（当前所有父行最大 Class + 1）。"""
    parent_classes = []
    for r in state:
        if r.get("_parent_id") is None:
            try:
                parent_classes.append(int(r.get("Class") or 0))
            except (ValueError, TypeError):
                parent_classes.append(0)
    return max(parent_classes, default=0) + 1
```

**Step 1: 修改为跳过标题行**

```python
def get_next_class(state: list[dict]) -> int:
    """计算新父行应得的 Class（当前所有非标题父行最大 Class + 1）。"""
    parent_classes = []
    for r in state:
        if r.get("_parent_id") is None and not r.get("_is_header"):
            try:
                parent_classes.append(int(r.get("Class") or 0))
            except (ValueError, TypeError):
                parent_classes.append(0)
    return max(parent_classes, default=0) + 1
```

**Step 2: Commit**

```bash
cd d:/shell_tool
git add web/dataset_editor.py
git commit -m "fix: get_next_class 跳过标题行，避免 Class 编号出现空隙"
```

---

## Task 3：`card_state_to_df` 按 state 位置顺序输出，排除断链行

**Files:**
- Modify: `web/dataset_editor.py`

**当前代码**（约第 87-115 行）：

```python
def card_state_to_df(state: list[dict]) -> pd.DataFrame:
    if not state:
        return pd.DataFrame(columns=DATASET_TABLE_COLS)

    # 父行按 Class 排序
    parents = sorted(
        [r for r in state if r.get("_parent_id") is None],
        key=lambda r: int(r.get("Class") or 0),
    )

    ordered: list[dict] = []
    for parent in parents:
        ordered.append(parent)
        children = sorted(
            [r for r in state if r.get("_parent_id") == parent["_id"]],
            key=lambda r: int(r.get("Order") or 0),
        )
        ordered.extend(children)

    rows = [_row_data(r) for r in ordered]
    df = pd.DataFrame(rows, columns=DATASET_TABLE_COLS)
    df["Order"] = pd.to_numeric(df["Order"], errors="coerce").fillna(0).astype(int)
    df["exclude"] = pd.to_numeric(df["exclude"], errors="coerce").fillna(0).astype(int)
    return df
```

**Step 1: 改为按 state 位置顺序，排除断链行**

```python
def card_state_to_df(state: list[dict]) -> pd.DataFrame:
    """
    card state → DataFrame。
    按 state 中出现顺序输出（不再按 Class 排序），每个父行后紧跟其子行。
    断链行（_parent_id=None, Order=1）不写入 DataFrame。
    """
    if not state:
        return pd.DataFrame(columns=DATASET_TABLE_COLS)

    # 按 state 位置顺序取父行，排除断链行（_parent_id=None, Order=1）
    parents = [
        r for r in state
        if r.get("_parent_id") is None
        and int(r.get("Order") or 0) == 0
    ]

    # 预建 parent_id → linked_children 索引，避免 O(n²)
    children_map: dict[str, list[dict]] = {}
    for r in state:
        pid = r.get("_parent_id")
        if pid is not None and r.get("_linked"):
            children_map.setdefault(pid, []).append(r)

    ordered: list[dict] = []
    for parent in parents:
        ordered.append(parent)
        children = sorted(
            children_map.get(parent["_id"], []),
            key=lambda r: int(r.get("Order") or 0),
        )
        ordered.extend(children)

    rows = [_row_data(r) for r in ordered]
    df = pd.DataFrame(rows, columns=DATASET_TABLE_COLS)
    df["Order"] = pd.to_numeric(df["Order"], errors="coerce").fillna(0).astype(int)
    df["exclude"] = pd.to_numeric(df["exclude"], errors="coerce").fillna(0).astype(int)
    return df
```

注意：`parents` 的过滤条件 `Order==0` 已天然排除断链行（断链行 `Order=1`）。

**Step 2: Commit**

```bash
cd d:/shell_tool
git add web/dataset_editor.py
git commit -m "fix: card_state_to_df 按位置顺序输出，排除断链行，预建子行索引"
```

---

## Task 4：R 端 `build_table_data` — 标题行（Class=0）不插前置空行

**Files:**
- Modify: `R/generators/generate_table.R`

**当前逻辑**（约第 99-109 行）：

```r
for (i in 1:nrow(dataset)) {
  current_class <- dataset$Class[i]
  if (!is.na(prev_class) && !is.na(current_class) && prev_class != current_class) {
    # 插空行
    ...
  }
  # 添加当前行
  ...
  prev_class <- current_class
}
```

标题行 `Class=0`，前一行 `Class!=0` 时会触发空行，标题行后一行 `Class=1` 时再触发一次空行，标题行被两个空行夹住。

**Step 1: 修改条件，Class=0 时不插前置空行**

找到 `# 如果Class变化且不是第一行，插入空行` 的 if 条件，改为：

```r
    # Class变化时插分隔空行；标题行（Class=0）前不插，由上一组变化自然触发
    if (!is.na(prev_class) && !is.na(current_class) &&
        prev_class != current_class && current_class != 0) {
      empty_row <- as.list(rep("", n_cols))
      names(empty_row) <- colnames(header)
      result_rows[[length(result_rows) + 1]] <- empty_row
      spacer_rows <- c(spacer_rows, length(result_rows))
    }
```

**Step 2: 标题行 Label 加粗**

在「添加当前行」→「Label 列」处，追加对 Class=0 行的加粗标记。找到：

```r
      if (col_idx == label_col_idx) {
        indent <- ifelse(is.na(dataset$Order[i]), 0, dataset$Order[i])
        spaces <- paste(rep("  ", indent), collapse = "")
        row_data[[col_idx]] <- paste0(spaces, dataset$Label[i])
```

改为：

```r
      if (col_idx == label_col_idx) {
        indent <- ifelse(is.na(dataset$Order[i]), 0, dataset$Order[i])
        spaces <- paste(rep("  ", indent), collapse = "")
        row_data[[col_idx]] <- paste0(spaces, dataset$Label[i])
```

（Label 内容不变，加粗通过 flextable 的格式化处理——见 Step 3）

**Step 3: 在 `create_flextable` 中对 Class=0 行加粗**

找到 `create_flextable` 函数，在三线表格式设置之后（`ft <- border_remove(ft)` 之后）加入：

```r
  # 标题行（Class=0）加粗
  if ("Class" %in% colnames(data)) {
    header_rows <- which(data$Class == 0)
    if (length(header_rows) > 0) {
      ft <- bold(ft, i = header_rows, bold = TRUE, part = "body")
    }
  }
```

**注意**：`create_flextable` 接收的 `data` 是 `build_table_data` 的返回值，其中仍然保留了 `Class` 列（通过 `attr(result, "spacer_rows")` 之类的方式传递）。需要检查 `data` 是否包含 `Class` 列——如果不包含，需要在 `build_table_data` 返回时把 `Class` 列附加到 result 上，或者用 `attr` 传递 header_rows 的行号。

实际查看代码：`build_table_data` 返回的 `result` 是由 `header` 的列名构建的，不含 `Class`。因此需要用 `attr` 传递标题行行号，与 `spacer_rows` 类似：

在 `build_table_data` 函数末尾（`attr(result, "spacer_rows") <- spacer_rows` 之后）追加：

```r
  header_rows <- which(dataset$Class == 0 & dataset$Order == 0)
  attr(result, "header_rows") <- header_rows
  return(result)
```

在 `create_flextable` 中读取：

```r
  header_rows <- attr(data, "header_rows")
  if (!is.null(header_rows) && length(header_rows) > 0) {
    ft <- bold(ft, i = header_rows, bold = TRUE, part = "body")
  }
```

**Step 4: Commit**

```bash
cd d:/shell_tool
git add R/generators/generate_table.R
git commit -m "fix: 标题行(Class=0)前不插空行，标题行 Label 加粗"
```

---

## Task 5：`_infer_var_types` 和相关函数预建索引，消除 O(n²)

**Files:**
- Modify: `web/dataset_editor.py`

**Step 1: 修改 `_infer_var_types`，预建 parent_id → children 索引**

当前约第 249-284 行：

```python
def _infer_var_types(state: list[dict]) -> list[dict]:
    result = []
    for row in state:
        if row.get("_parent_id") is not None:
            result.append(row)
            continue
        if row.get("_var_type", VAR_TYPE_DEFAULT) != VAR_TYPE_DEFAULT:
            result.append(row)
            continue

        parent_id = row["_id"]
        children = [r for r in state if r.get("_parent_id") == parent_id and r.get("_linked")]
        ...
```

改为先建索引，再遍历：

```python
def _infer_var_types(state: list[dict]) -> list[dict]:
    """
    根据子行数量和 Aval 模式推断父行的 _var_type。
    仅对 _var_type == '手动输入' 的父行生效，有明确类型的不覆盖。
    """
    # 预建 parent_id → linked_children 索引，避免 O(n²)
    children_map: dict[str, list[dict]] = {}
    for r in state:
        pid = r.get("_parent_id")
        if pid is not None and r.get("_linked"):
            children_map.setdefault(pid, []).append(r)

    result = []
    for row in state:
        if row.get("_parent_id") is not None:
            result.append(row)
            continue
        if row.get("_var_type", VAR_TYPE_DEFAULT) != VAR_TYPE_DEFAULT:
            result.append(row)
            continue

        parent_id = row["_id"]
        children = children_map.get(parent_id, [])
        n_children = len(children)

        if n_children == 0:
            aval = str(row.get("Aval") or "").strip()
            if aval and _aval_is_categorical(aval):
                inferred = "分类变量-无子分类"
            else:
                inferred = VAR_TYPE_DEFAULT
        else:
            child_avals = [str(c.get("Aval") or "").strip() for c in children]
            non_empty = [a for a in child_avals if a and not _aval_is_count(a)]
            if non_empty and all(_aval_is_continuous(a) for a in non_empty):
                inferred = "连续变量"
            elif non_empty and all(_aval_is_categorical(a) for a in non_empty):
                inferred = "分类变量-有子分类"
            else:
                inferred = VAR_TYPE_DEFAULT

        result.append({**row, "_var_type": inferred})
    return result
```

**Step 2: 修改 `_infer_is_header`，预建索引**

当前约第 405-429 行，内层有 `any(r.get("_parent_id") == parent_id ...)` 全量扫描：

```python
def _infer_is_header(state: list[dict]) -> list[dict]:
    # 预建 parent_id → has_linked_children 集合
    parents_with_children: set[str] = {
        r["_parent_id"] for r in state
        if r.get("_parent_id") is not None and r.get("_linked")
    }

    result = []
    for row in state:
        if row.get("_parent_id") is not None:
            result.append(row)
            continue
        if int(row.get("Order") or 0) != 0:
            result.append(row)
            continue
        has_linked_children = row["_id"] in parents_with_children
        if has_linked_children:
            result.append({**row, "_is_header": False})
        else:
            aval = str(row.get("Aval") or "").strip()
            label = str(row.get("Label") or "").strip()
            inferred = (aval == "" and label != "")
            result.append({**row, "_is_header": inferred})
    return result
```

**Step 3: 修改 `normalize_dataset_state`，预建索引**

当前约第 333-335 行有 `[r for r in state if r.get("_parent_id") == parent_id and r.get("_linked")]` 内层扫描：

在函数开头加索引：

```python
def normalize_dataset_state(state: list[dict], templates: dict) -> tuple[list[dict], list[dict]]:
    # 预建 parent_id → linked_children 索引
    children_map: dict[str, list[dict]] = {}
    for r in state:
        pid = r.get("_parent_id")
        if pid is not None and r.get("_linked"):
            children_map.setdefault(pid, []).append(r)

    conflicts = []
    for row in state:
        if row.get("_parent_id") is not None:
            continue
        vtype = row.get("_var_type", VAR_TYPE_DEFAULT)
        if vtype == VAR_TYPE_DEFAULT:
            continue
        tmpl = templates.get(vtype, {})
        parent_id = row["_id"]
        parent_label = str(row.get("Label") or "")

        # 父行自身 Aval
        tmpl_parent_aval = tmpl.get("aval", "")
        if tmpl_parent_aval:
            cur = str(row.get("Aval") or "").strip()
            if cur != tmpl_parent_aval:
                conflicts.append({
                    "parent_id": parent_id, "parent_label": parent_label,
                    "var_type": vtype, "child_id": None,
                    "child_label": f"[父行] {parent_label}",
                    "current_aval": cur, "template_aval": tmpl_parent_aval, "apply": True,
                })

        tmpl_children = tmpl.get("children", [])
        linked_children = children_map.get(parent_id, [])   # ← 用索引替代全量扫描

        for i, child in enumerate(linked_children):
            cur = str(child.get("Aval") or "").strip()
            if vtype == "分类变量-有子分类":
                aval_opts = tmpl.get("aval_options", [])
                tmpl_aval = aval_opts[0] if aval_opts else "xx (xx.x)"
                if cur == tmpl_aval:
                    continue
            elif i < len(tmpl_children):
                tmpl_aval = str(tmpl_children[i].get("Aval") or "").strip()
                if not tmpl_aval or cur == tmpl_aval:
                    continue
            else:
                continue
            conflicts.append({
                "parent_id": parent_id, "parent_label": parent_label,
                "var_type": vtype, "child_id": child["_id"],
                "child_label": str(child.get("Label") or f"子行 {i+1}"),
                "current_aval": cur, "template_aval": tmpl_aval, "apply": True,
            })

    return state, conflicts
```

**Step 4: Commit**

```bash
cd d:/shell_tool
git add web/dataset_editor.py
git commit -m "perf: _infer_var_types/_infer_is_header/normalize_dataset_state 预建索引消除 O(n²)"
```

---

## Task 6：批量生成分类变量子行 Aval 从模板读取

**Files:**
- Modify: `web/dataset_editor.py`

**当前代码**（约第 849-858 行）：

```python
if st.button("确认生成子行", key=f"subclass_ok_{row_id}", type="primary"):
    names = [n.strip() for n in subclass_text.splitlines() if n.strip()]
    cls = row.get("Class", 0)
    aval_val = "xx (xx.x)"   # ← 硬编码
    new_children = []
    for name in names:
        child_data = _new_data_row(class_val=cls, order=1)
        child_data["Label"] = name
        child_data["Aval"] = aval_val
```

**Step 1: 改为从模板读取**

```python
if st.button("确认生成子行", key=f"subclass_ok_{row_id}", type="primary"):
    names = [n.strip() for n in subclass_text.splitlines() if n.strip()]
    cls = row.get("Class", 0)
    aval_opts = templates.get("分类变量-有子分类", {}).get("aval_options", [])
    aval_val = aval_opts[0] if aval_opts else "xx (xx.x)"
    new_children = []
    for name in names:
        child_data = _new_data_row(class_val=cls, order=1)
        child_data["Label"] = name
        child_data["Aval"] = aval_val
```

**Step 2: Commit**

```bash
cd d:/shell_tool
git add web/dataset_editor.py
git commit -m "fix: 批量生成分类变量子行 Aval 从模板读取而非硬编码"
```

---

## Task 7：「更多字段」修改后统一加 `st.rerun()`

**Files:**
- Modify: `web/dataset_editor.py`

**当前代码**（约第 916-961 行，`更多字段` expander 内）：

exclude、BlankCol、Drug、Visit、Base 的 `if new_x != cur_x: st.session_state[key] = [...]` 之后都没有 `st.rerun()`，行为与其他字段不一致。

**Step 1: 在每个字段的 `if` 块末尾加 `st.rerun()`**

5 处，每处模式一样：

```python
                if new_excl != cur_excl:
                    st.session_state[key] = [
                        {**r, "exclude": new_excl} if r["_id"] == row_id else r
                        for r in st.session_state[key]
                    ]
                    st.rerun()   # ← 添加
```

同理为 BlankCol、Drug、Visit、Base 的 `if` 块各加一行 `st.rerun()`。

**同样处理主行 Label**（约第 707-711 行）和子行 Label（约第 980-984 行），当前也没有 `st.rerun()`，一并补上。

**Step 2: Commit**

```bash
cd d:/shell_tool
git add web/dataset_editor.py
git commit -m "fix: 字段修改后统一调用 st.rerun()，保持行为一致性"
```

---

## Task 8：子行 Order 支持 1-5 多级缩进

**Files:**
- Modify: `web/dataset_editor.py`

**当前**：子行渲染时 Class 列只读（`disabled=True`），Order 字段完全不展示。

**Step 1: 在子行渲染区（`cc_link, cc_class, cc_label, cc_aval, cc_unlink` 布局）中增加 Order 列**

找到约第 964-966 行：

```python
                    cc_link, cc_class, cc_label, cc_aval, cc_unlink = st.columns([0.4, 1, 3, 3, 1.5])
```

改为 6 列，加入 Order：

```python
                    cc_link, cc_class, cc_order, cc_label, cc_aval, cc_unlink = st.columns([0.4, 0.8, 0.8, 2.8, 3, 1.5])
```

在 `with cc_order:` 中渲染：

```python
                    with cc_order:
                        cur_order = int(child.get("Order") or 1)
                        new_order = st.number_input(
                            "Order", value=cur_order,
                            min_value=1, max_value=5, step=1,
                            label_visibility="collapsed",
                            key=f"child_order_{child_id}",
                        )
                        if new_order != cur_order:
                            st.session_state[key] = [
                                {**r, "Order": new_order} if r["_id"] == child_id else r
                                for r in st.session_state[key]
                            ]
                            st.rerun()
```

**Step 2: Commit**

```bash
cd d:/shell_tool
git add web/dataset_editor.py
git commit -m "feat: 子行支持编辑 Order(1-5) 多级缩进"
```

---

## Task 9：新行临时 Class 用 -1 替代 0 作为哨兵值

**Files:**
- Modify: `web/dataset_editor.py`

**问题**：`insert_after` 新行 `Class=0`，而 0 现在是标题行的语义值，两者混用有歧义。

**Step 1: 修改 `insert_after`，新行先用 -1，`_reindex_class` 之后自动修正**

找到约第 511-519 行：

```python
def insert_after(state: list[dict], parent_id: str) -> list[dict]:
    _, end = _group_slice(state, parent_id)
    new_row = _new_data_row(class_val=0, order=0) | _new_meta()
    new_state = state[:end] + [new_row] + state[end:]
    return _reindex_class(new_state)
```

改为：

```python
def insert_after(state: list[dict], parent_id: str) -> list[dict]:
    _, end = _group_slice(state, parent_id)
    new_row = _new_data_row(class_val=-1, order=0) | _new_meta()  # -1 为待分配哨兵
    new_state = state[:end] + [new_row] + state[end:]
    return _reindex_class(new_state)
```

同理修改 `add_parent_row`（约第 136-140 行）：

```python
def add_parent_row(state: list[dict]) -> list[dict]:
    """在末尾追加一个新父行，Class = max父行Class + 1。"""
    cls = get_next_class(state)
    row = _new_data_row(class_val=cls, order=0) | _new_meta()
    return state + [row]
```

`add_parent_row` 已经调 `get_next_class`（Task 2 修复后已跳过标题行），不需要用 -1，保持不变。只改 `insert_after` 即可，因为它之后立刻调 `_reindex_class`，中间状态不会被读取。实际上改 `class_val=-1` 还是 `class_val=0` 对结果没有区别（`_reindex_class` 会覆盖），只是语义更清晰。

**Step 2: Commit**

```bash
cd d:/shell_tool
git add web/dataset_editor.py
git commit -m "refactor: insert_after 新行用 class_val=-1 哨兵值，语义更清晰"
```

---

## Task 10：`_smart_promote_children` 清除提升行的 Class，依赖 `_reindex_class` 重排

**Files:**
- Modify: `web/dataset_editor.py`

**当前**（约第 378-401 行）：提升的行沿用子行的旧 Class，与原父行 Class 相同，`_reindex_class` 之后能正确修正，但中间状态有歧义。

**Step 1: 提升时将 Class 置 -1**

```python
def _smart_promote_children(state: list[dict], parent_id: str) -> list[dict]:
    """
    将父行的 linked 子行智能提升：
    - Aval=空 → 新父行（Order=0，独立，Class=-1 待 _reindex_class 分配）
    - Aval=非空 → 归属到前一个新父行的 linked 子行（Order=1）
    - 若首行 Aval=非空且无前置新父行，也提升为独立父行
    """
    children = [r for r in state if r.get("_parent_id") == parent_id and r.get("_linked")]
    promoted = []
    current_new_parent_id = None

    for child in children:
        aval = str(child.get("Aval") or "").strip()
        if aval == "":
            new_row = {**child, "_parent_id": None, "_linked": False, "Order": 0, "Class": -1}
            current_new_parent_id = new_row["_id"]
        else:
            if current_new_parent_id is not None:
                new_row = {**child, "_parent_id": current_new_parent_id, "_linked": True, "Order": 1}
            else:
                new_row = {**child, "_parent_id": None, "_linked": False, "Order": 0, "Class": -1}
                current_new_parent_id = new_row["_id"]
        promoted.append(new_row)

    return promoted
```

**Step 2: Commit**

```bash
cd d:/shell_tool
git add web/dataset_editor.py
git commit -m "refactor: _smart_promote_children 提升行 Class 置 -1，语义清晰"
```

---

## Task 11：最终验证与 Push

**Step 1: 启动 Streamlit 验证**

```bash
cd d:/shell_tool
streamlit run web/app.py --server.port 8501
```

**手动验证清单：**

1. 新建数据集，添加标题行（📌），添加变量行，点「🔧 自动矫正」→ 标题行 Class=0，变量行 Class=1、2...
2. 标题行前后各只有一个空行（标题行后紧接数据行，无多余空行）
3. 移动变量行（▲/▼），Class 随位置重排，标题行 Class 始终为 0
4. 「切换为标题行 → 子行转为父行」后，`_reindex_class` 正确重排
5. 断链行不出现在 YAML 预览中（生成 YAML 预览验证）
6. 分类变量-有子分类批量生成子行，Aval 跟随模板配置
7. 修改「更多字段」中的 exclude/BlankCol/Drug/Visit/Base，页面立即刷新

**Step 2: Push**

```bash
cd d:/shell_tool
git push origin master
```
