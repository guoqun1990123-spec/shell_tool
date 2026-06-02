# Dataset Label/Aval UX & Logic Fixes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 修复 Datasets 编辑器中 Label/Aval 填充逻辑的 8 个问题，重点消除文本输入卡顿、修正矫正逻辑、补全遗漏功能。

**Architecture:** 所有修改集中在 `web/dataset_editor.py`。性能改进通过 `on_change` 回调替代每轮比较+rerun；逻辑修复包括 `_var_type_locked` 标记、矫正改 Label 匹配、父行 Aval radio 读模板、UI 层预建索引；功能补全包括子行插入按钮和批量设 Aval。

**Tech Stack:** Python 3, Streamlit, pandas

---

## 背景：Streamlit on_change 机制

`st.text_input` 的 `on_change` 回调在用户**离焦（Tab/点击其他地方）或按 Enter** 时触发，触发时 widget 的当前值已写入 `st.session_state[key]`，回调函数可直接读取。触发后 Streamlit 自动 rerun 一次。打字过程中不触发，彻底解决每按键一次 rerun 的卡顿问题。

`on_change` 回调签名：`def callback(...):`，通过 `args=(...)` 传参。

---

## Task 1：`_new_meta` 增加 `_var_type_locked` 字段，`_infer_var_types` 只推断未锁定的行

**Files:**
- Modify: `web/dataset_editor.py`

**背景：** 目前 `_infer_var_types` 对所有 `_var_type == "手动输入"` 的父行进行推断，但用户手动切换过类型后也会被再次推断覆盖。引入 `_var_type_locked` 标记区分「用户显式设置」和「未设置」。

**Step 1: 修改 `_new_meta`，增加 `_var_type_locked=False` 字段**

找到约第 14-28 行的 `_new_meta` 函数，在返回 dict 中追加：
```python
def _new_meta(
    var_type: str = VAR_TYPE_DEFAULT,
    parent_id: str | None = None,
    linked: bool = False,
    expanded: bool = True,
    is_header: bool = False,
) -> dict:
    return {
        "_id": str(uuid.uuid4()),
        "_var_type": var_type,
        "_var_type_locked": False,   # 新增：用户显式切换后置 True，不再被 _infer_var_types 覆盖
        "_parent_id": parent_id,
        "_linked": linked,
        "_expanded": expanded,
        "_is_header": is_header,
    }
```

**Step 2: `df_to_card_state` 加载时 `_var_type_locked=False`**

找到约第 64-73 行 `df_to_card_state` 中的父行 meta 创建：
```python
        if order == 0:
            meta = _new_meta(var_type=VAR_TYPE_DEFAULT, parent_id=None, linked=False)
```
`_new_meta` 已默认 `_var_type_locked=False`，此处无需改动。

**Step 3: `_infer_var_types` 只推断 `_var_type_locked=False` 的行**

找到约第 274 行的跳过条件：
```python
        if row.get("_var_type", VAR_TYPE_DEFAULT) != VAR_TYPE_DEFAULT:
            result.append(row)
            continue
```
改为同时跳过已锁定的行：
```python
        if row.get("_var_type_locked") or row.get("_var_type", VAR_TYPE_DEFAULT) != VAR_TYPE_DEFAULT:
            result.append(row)
            continue
```

**Step 4: 用户手动切换 `_var_type` 时置 `_var_type_locked=True`**

找到 `render_dataset_editor` 中 `expand_var_type` 的调用处（约第 756-762 行）：
```python
                        else:
                            st.session_state[key] = expand_var_type(
                                st.session_state[key], row_id, new_type, templates
                            )
                            if new_type == "分类变量-有子分类":
                                st.session_state[pending_sub_key] = ""
                            st.rerun()
```
在 `expand_var_type` 调用后立即加锁：
```python
                        else:
                            new_state = expand_var_type(
                                st.session_state[key], row_id, new_type, templates
                            )
                            # 用户显式切换类型，锁定不再被自动推断覆盖
                            new_state = [
                                {**r, "_var_type_locked": True} if r["_id"] == row_id else r
                                for r in new_state
                            ]
                            st.session_state[key] = new_state
                            if new_type == "分类变量-有子分类":
                                st.session_state[pending_sub_key] = ""
                            st.rerun()
```

同理，「保留现有子行」分支（约第 806-820 行）也要加锁：
```python
            with col_keep:
                if st.button("保留现有子行", key=f"vt_keep_{row_id}"):
                    st.session_state[key] = [
                        {**r, "_var_type": new_vt, "_var_type_locked": True}
                        if r["_id"] == row_id else r
                        for r in st.session_state[key]
                    ]
```

**Step 5: Commit**
```bash
cd d:/shell_tool
git add web/dataset_editor.py
git commit -m "fix: _var_type_locked 防止用户设置的变量类型被 _infer_var_types 覆盖"
```

---

## Task 2：`normalize_dataset_state` 连续变量子行改为按 Label 匹配

**Files:**
- Modify: `web/dataset_editor.py`

**背景：** 当前按位置（`enumerate` 下标 `i`）匹配模板子行，子行顺序变化后会把错误的 Aval 写到错误的子行。改为按 Label 匹配，找不到对应 Label 则跳过（不矫正）。

**Step 1: 找到 `normalize_dataset_state` 中子行矫正逻辑**

约第 354-382 行，当前：
```python
        tmpl_children = tmpl.get("children", [])
        linked_children = children_map.get(parent_id, [])

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
```

**Step 2: 改为按 Label 匹配模板**

```python
        # 预建模板子行的 Label→Aval 映射，用于按 Label 匹配而非位置匹配
        tmpl_children = tmpl.get("children", [])
        tmpl_by_label: dict[str, str] = {
            str(c.get("Label") or "").strip(): str(c.get("Aval") or "").strip()
            for c in tmpl_children
            if c.get("Label") and c.get("Aval")
        }
        linked_children = children_map.get(parent_id, [])

        for child in linked_children:
            cur = str(child.get("Aval") or "").strip()

            if vtype == "分类变量-有子分类":
                aval_opts = tmpl.get("aval_options", [])
                tmpl_aval = aval_opts[0] if aval_opts else "xx (xx.x)"
                if cur == tmpl_aval:
                    continue
            else:
                # 按 Label 在模板中查找期望 Aval；找不到说明是用户自定义子行，跳过
                child_label = str(child.get("Label") or "").strip()
                if child_label not in tmpl_by_label:
                    continue
                tmpl_aval = tmpl_by_label[child_label]
                if not tmpl_aval or cur == tmpl_aval:
                    continue
```

**Step 3: Commit**
```bash
cd d:/shell_tool
git add web/dataset_editor.py
git commit -m "fix: normalize_dataset_state 连续变量子行按 Label 匹配模板，避免位置错位误矫正"
```

---

## Task 3：父行 Aval radio 从模板读取选项

**Files:**
- Modify: `web/dataset_editor.py`

**背景：** 约第 765-779 行，父行 Aval radio 硬编码 `["空", "xx (xx.x)"]`，用户在模板配置里改了 `aval_options` 后 radio 不跟随，导致反复矫正。

**Step 1: 找到父行 Aval radio 渲染逻辑（约第 764-779 行）**

当前：
```python
                with c_aval:
                    if cur_type == "分类变量-有子分类":
                        cur_aval = str(row.get("Aval") or "")
                        aval_options = ["空", "xx (xx.x)"]
                        aval_idx = 1 if cur_aval == "xx (xx.x)" else 0
                        sel_aval = st.radio(
                            "父行Aval", options=aval_options, index=aval_idx,
                            key=f"parent_aval_{row_id}", label_visibility="collapsed",
                            horizontal=True,
                        )
                        new_aval_val = "" if sel_aval == "空" else "xx (xx.x)"
```

**Step 2: 改为从模板读取选项**

```python
                with c_aval:
                    if cur_type == "分类变量-有子分类":
                        cur_aval = str(row.get("Aval") or "")
                        # 从模板读取候选值，而非硬编码
                        tmpl_aval_opts = templates.get("分类变量-有子分类", {}).get("aval_options", ["xx (xx.x)"])
                        radio_opts = ["空"] + tmpl_aval_opts
                        # 当前值在候选中找到则选中，否则选「空」
                        if cur_aval and cur_aval in tmpl_aval_opts:
                            radio_idx = tmpl_aval_opts.index(cur_aval) + 1  # +1 因为「空」在首位
                        else:
                            radio_idx = 0
                        sel_aval = st.radio(
                            "父行Aval", options=radio_opts, index=radio_idx,
                            key=f"parent_aval_{row_id}", label_visibility="collapsed",
                            horizontal=True,
                        )
                        new_aval_val = "" if sel_aval == "空" else sel_aval
```

**Step 3: Commit**
```bash
cd d:/shell_tool
git add web/dataset_editor.py
git commit -m "fix: 父行 Aval radio 从模板 aval_options 读取选项，不再硬编码"
```

---

## Task 4：UI 层渲染循环预建 linked_children 索引

**Files:**
- Modify: `web/dataset_editor.py`

**背景：** `render_dataset_editor` 的父行渲染循环（约第 638-645 行）中：
```python
linked_children = [r for r in state if r.get("_parent_id") == row_id and r.get("_linked")]
```
每个父行都全量扫描 state，O(n²)。虽然纯函数层已优化，UI 层漏掉了。

**Step 1: 在父行渲染循环开始前（`for row in state:` 之前，约第 638 行）预建索引**

找到：
```python
    state = st.session_state[key]

    # 计算父行列表（用于边界判断）
    parent_ids = [r["_id"] for r in state if r.get("_parent_id") is None and int(r.get("Order") or 0) == 0]

    for row in state:
```

改为：
```python
    state = st.session_state[key]

    # 计算父行列表（用于边界判断）
    parent_ids = [r["_id"] for r in state if r.get("_parent_id") is None and int(r.get("Order") or 0) == 0]

    # 预建 UI 层索引，避免渲染循环内 O(n²) 扫描
    _ui_children_map: dict[str, list[dict]] = {}
    for _r in state:
        _pid = _r.get("_parent_id")
        if _pid is not None and _r.get("_linked"):
            _ui_children_map.setdefault(_pid, []).append(_r)

    for row in state:
```

**Step 2: 将循环体内的 `linked_children` 计算改为查索引**

找到约第 645 行：
```python
        linked_children = [r for r in state if r.get("_parent_id") == row_id and r.get("_linked")]
```
改为：
```python
        linked_children = _ui_children_map.get(row_id, [])
```

**Step 3: Commit**
```bash
cd d:/shell_tool
git add web/dataset_editor.py
git commit -m "perf: render_dataset_editor UI 层预建 linked_children 索引消除 O(n²)"
```

---

## Task 5：Label 和 Aval 文本输入改为 on_change 回调，消除打字卡顿

**Files:**
- Modify: `web/dataset_editor.py`

**背景：** 以下 text_input 当前在每轮 rerun 中比较值，值变化则写 state + rerun，导致每次按键都触发一次全量刷新。改用 `on_change` 回调后，只有离焦或按 Enter 才触发，打字过程流畅。

涉及的控件：
- 父行 Label（约第 725-737 行）
- 子行 Label（约第 1020-1031 行）
- 子行 Aval text_input 版本（约第 1060-1070 行）
- 「更多字段」中的 BlankCol、Drug、Visit、Base（约第 929-993 行）

**Step 1: 在 `render_dataset_editor` 函数顶部定义通用回调**

在函数体开头（`state = _ensure_card_state(...)` 之前）定义：
```python
    def _update_field(widget_key: str, state_key: str, row_id: str, field: str) -> None:
        """text_input on_change 回调：将 widget 当前值写回对应行的 field。"""
        new_val = st.session_state.get(widget_key, "")
        st.session_state[state_key] = [
            {**r, field: new_val} if r["_id"] == row_id else r
            for r in st.session_state[state_key]
        ]
```

**Step 2: 父行 Label 改用 on_change（约第 725-737 行）**

当前：
```python
            with c_label:
                new_label = st.text_input(
                    "Label", value=str(row.get("Label") or ""),
                    placeholder="小节标题" if is_header else "变量名称",
                    label_visibility="collapsed",
                    key=f"label_{row_id}"
                )
                if new_label != str(row.get("Label") or ""):
                    st.session_state[key] = [
                        {**r, "Label": new_label} if r["_id"] == row_id else r
                        for r in st.session_state[key]
                    ]
                    st.rerun()
```

改为：
```python
            with c_label:
                st.text_input(
                    "Label", value=str(row.get("Label") or ""),
                    placeholder="小节标题" if is_header else "变量名称",
                    label_visibility="collapsed",
                    key=f"label_{row_id}",
                    on_change=_update_field,
                    args=(f"label_{row_id}", key, row_id, "Label"),
                )
```

**Step 3: 子行 Label 改用 on_change（约第 1020-1031 行）**

当前：
```python
                    with cc_label:
                        new_child_label = st.text_input(
                            "Label", value=str(child.get("Label") or ""),
                            label_visibility="collapsed",
                            key=f"child_label_{child_id}"
                        )
                        if new_child_label != str(child.get("Label") or ""):
                            st.session_state[key] = [
                                {**r, "Label": new_child_label} if r["_id"] == child_id else r
                                for r in st.session_state[key]
                            ]
                            st.rerun()
```

改为：
```python
                    with cc_label:
                        st.text_input(
                            "Label", value=str(child.get("Label") or ""),
                            label_visibility="collapsed",
                            key=f"child_label_{child_id}",
                            on_change=_update_field,
                            args=(f"child_label_{child_id}", key, child_id, "Label"),
                        )
```

**Step 4: 子行 Aval text_input 版（约第 1060-1070 行，无 aval_options 时）**

当前：
```python
                        else:
                            new_aval = st.text_input(
                                "Aval", value=cur_child_aval,
                                label_visibility="collapsed",
                                key=f"child_aval_{child_id}"
                            )
                        if new_aval != cur_child_aval:
                            st.session_state[key] = [
                                {**r, "Aval": new_aval} if r["_id"] == child_id else r
                                for r in st.session_state[key]
                            ]
```

改为（注意 `if new_aval != cur_child_aval` 的处理需要保留 selectbox 版本的写回，只改 text_input 分支）：

将 `else:` 分支改为：
```python
                        else:
                            st.text_input(
                                "Aval", value=cur_child_aval,
                                label_visibility="collapsed",
                                key=f"child_aval_{child_id}",
                                on_change=_update_field,
                                args=(f"child_aval_{child_id}", key, child_id, "Aval"),
                            )
```

同时将原来的 `if new_aval != cur_child_aval:` 写回块改为**只处理 selectbox 的情况**（当 `aval_opts_for_child` 非空时）：
```python
                        if aval_opts_for_child:
                            # selectbox 版：sel 变化时写回（on_change 不适用于 selectbox）
                            if new_aval != cur_child_aval:
                                st.session_state[key] = [
                                    {**r, "Aval": new_aval} if r["_id"] == child_id else r
                                    for r in st.session_state[key]
                                ]
                        # text_input 版由 on_change 回调处理，无需此处写回
```

**Step 5: 「更多字段」中 BlankCol / Drug / Visit / Base 改用 on_change（约第 929-993 行）**

每个字段当前模式：
```python
                cur_bc = str(row.get("BlankCol") or "")
                new_bc = ef2.text_input("BlankCol", value=cur_bc,
                                        key=f"blankcol_{row_id}",
                                        placeholder="如 1|2")
                if new_bc != cur_bc:
                    st.session_state[key] = [
                        {**r, "BlankCol": new_bc} if r["_id"] == row_id else r
                        for r in st.session_state[key]
                    ]
                    st.rerun()
```

改为：
```python
                ef2.text_input("BlankCol", value=str(row.get("BlankCol") or ""),
                               key=f"blankcol_{row_id}",
                               placeholder="如 1|2",
                               on_change=_update_field,
                               args=(f"blankcol_{row_id}", key, row_id, "BlankCol"))
```

同理处理 Drug、Visit、Base（各自的字段名和 key 前缀对应替换）：
- Drug: `key=f"drug_{row_id}"`, `field="Drug"`
- Visit: `key=f"visit_{row_id}"`, `field="Visit"`
- Base: `key=f"base_{row_id}"`, `field="Base"`

`exclude` 是 selectbox，保持原有写回方式（selectbox 的 `on_change` 写法类似，但 `st.rerun()` 还是需要，保持不动）。

**Step 6: Commit**
```bash
cd d:/shell_tool
git add web/dataset_editor.py
git commit -m "perf: Label/Aval/更多字段 改用 on_change 回调，消除打字触发 rerun 卡顿"
```

---

## Task 6：静态预览结果缓存

**Files:**
- Modify: `web/dataset_editor.py`（`_ensure_card_state` 或 `render_dataset_editor` 中）
- Modify: `web/config_editor.py`（`_render_card_preview` 中）

**背景：** `_render_card_preview` 每次 rerun 都调用 `render_preview(cur_card, datasets)` 重新生成 HTML。改为用 `session_state` 缓存，key 为 `_preview_html_{card_id}`，只有 card 内容或对应 dataset 内容变化时才重新生成。

**Step 1: 修改 `_render_card_preview`（`web/config_editor.py` 约第 582-617 行）**

找到函数开头：
```python
def _render_card_preview(card: dict, card_id: str, version: int) -> None:
    datasets = st.session_state.get("datasets", {})
    card_state = st.session_state.get(_CARD_STATE_KEY, [])
    cur_card = next((c for c in card_state if c["_id"] == card_id), card)

    html = _tfl_preview.render_preview(cur_card, datasets)
    st.markdown(html, unsafe_allow_html=True)
```

改为用 session_state 缓存，以 card 数据和 dataset 数据的内容 hash 作为 cache key：

```python
def _render_card_preview(card: dict, card_id: str, version: int) -> None:
    import hashlib, json
    datasets = st.session_state.get("datasets", {})
    card_state = st.session_state.get(_CARD_STATE_KEY, [])
    cur_card = next((c for c in card_state if c["_id"] == card_id), card)

    # 计算轻量 cache key：card 数据字段 + 对应 dataset 的行数和列名
    ds_name = str(cur_card.get("Datasets") or "")
    ds = datasets.get(ds_name)
    ds_sig = f"{len(ds)}_{list(ds.columns)}" if ds is not None and not ds.empty else "empty"
    card_sig = json.dumps(
        {k: v for k, v in cur_card.items() if not k.startswith("_")},
        ensure_ascii=False, sort_keys=True
    )
    cache_key = f"_preview_html_{card_id}"
    sig_key   = f"_preview_sig_{card_id}"
    current_sig = hashlib.md5((card_sig + ds_sig).encode()).hexdigest()

    if st.session_state.get(sig_key) != current_sig:
        html = _tfl_preview.render_preview(cur_card, datasets)
        st.session_state[cache_key] = html
        st.session_state[sig_key]   = current_sig
    else:
        html = st.session_state[cache_key]

    st.markdown(html, unsafe_allow_html=True)
```

**Step 2: Commit**
```bash
cd d:/shell_tool
git add web/config_editor.py
git commit -m "perf: 静态预览 HTML 结果缓存，内容不变时跳过重新生成"
```

---

## Task 7：连续变量子行增加「在此后插入子行」按钮

**Files:**
- Modify: `web/dataset_editor.py`

**背景：** 连续变量模板给出四个固定子行，用户无法在子行列表中直接插入额外子行（如「几何均值」）。在每个 linked 子行的 `cc_unlink` 列旁边增加一个「＋」按钮，在当前子行后插入一个空白 linked 子行。

**Step 1: 修改子行列布局，增加插入按钮列**

找到约第 997 行：
```python
                    cc_link, cc_class, cc_order, cc_label, cc_aval, cc_unlink = st.columns([0.4, 0.8, 0.8, 2.8, 3, 1.5])
```
改为 7 列（增加 `cc_ins`）：
```python
                    cc_link, cc_class, cc_order, cc_label, cc_aval, cc_ins, cc_unlink = st.columns([0.4, 0.8, 0.8, 2.8, 3, 0.6, 1.5])
```

**Step 2: 在 `with cc_unlink:` 之前插入 `with cc_ins:` 块**

```python
                    with cc_ins:
                        if st.button("＋", key=f"child_ins_{child_id}", help="在此后插入子行"):
                            parent_cls = int(row.get("Class") or 0)
                            new_child_data = _new_data_row(class_val=parent_cls, order=1)
                            new_child_meta = _new_meta(parent_id=row_id, linked=True)
                            new_child = {**new_child_data, **new_child_meta}
                            # 找到当前子行在 state 中的位置，在其后插入
                            cur_state = st.session_state[key]
                            child_pos = next(
                                (i for i, r in enumerate(cur_state) if r["_id"] == child_id),
                                None
                            )
                            if child_pos is not None:
                                st.session_state[key] = (
                                    cur_state[:child_pos + 1] + [new_child] + cur_state[child_pos + 1:]
                                )
                            st.rerun()
```

**Step 3: Commit**
```bash
cd d:/shell_tool
git add web/dataset_editor.py
git commit -m "feat: 连续变量子行增加「在此后插入子行」按钮"
```

---

## Task 8：子行列表顶部增加「批量设 Aval」

**Files:**
- Modify: `web/dataset_editor.py`

**背景：** 分类变量-有子分类批量生成子行后，子行 Aval 均相同，但如果需要统一修改（如从 `"xx (xx.x)"` 改为 `"n (%)"`），目前只能逐行修改。在展开的子行列表上方增加一行批量控件。

**Step 1: 在子行渲染循环（`for child in linked_children:`）之前，当 `linked_children` 非空时插入批量控件**

找到约第 994 行 `for child in linked_children:` 之前：

```python
            if linked_children and not is_header:
                # ── 批量设 Aval ─────────────────────────────────────
                _bulk_aval_key = f"bulk_aval_{row_id}"
                _bulk_opts = templates.get(row.get("_var_type", VAR_TYPE_DEFAULT), {}).get("aval_options", [])
                bc1, bc2, bc3 = st.columns([2, 2, 1.5])
                with bc1:
                    st.caption("批量设子行 Aval：")
                with bc2:
                    if _bulk_opts:
                        _CUSTOM_BULK = "✏️ 自定义"
                        bulk_sel = st.selectbox(
                            "批量Aval", options=_bulk_opts + [_CUSTOM_BULK],
                            key=f"bulk_aval_sel_{row_id}",
                            label_visibility="collapsed",
                        )
                        if bulk_sel == _CUSTOM_BULK:
                            bulk_val = st.text_input(
                                "自定义批量Aval", key=f"bulk_aval_custom_{row_id}",
                                label_visibility="collapsed",
                            )
                        else:
                            bulk_val = bulk_sel
                    else:
                        bulk_val = st.text_input(
                            "批量Aval", key=_bulk_aval_key,
                            label_visibility="collapsed", placeholder="输入后点应用"
                        )
                with bc3:
                    if st.button("应用到所有子行", key=f"bulk_aval_apply_{row_id}",
                                 disabled=not bulk_val):
                        child_ids = {c["_id"] for c in linked_children}
                        st.session_state[key] = [
                            {**r, "Aval": bulk_val} if r["_id"] in child_ids else r
                            for r in st.session_state[key]
                        ]
                        # 清除子行 Aval 的 widget key，防止旧值覆盖
                        for c in linked_children:
                            for wk in (f"child_aval_{c['_id']}", f"child_aval_sel_{c['_id']}"):
                                if wk in st.session_state:
                                    del st.session_state[wk]
                        st.rerun()
```

**Step 2: Commit**
```bash
cd d:/shell_tool
git add web/dataset_editor.py
git commit -m "feat: 子行列表顶部增加批量设 Aval 控件"
```

---

## Task 9：最终验证与 Push

**Step 1: 手动验证清单**

1. **打字流畅**：在 Label 字段连续输入多个字符，页面不应每按键一次刷新；离焦后值保存
2. **类型锁定**：切换一个变量为「连续变量」→ 保存 YAML → 重新加载 → 该变量类型不变（不被 `_infer_var_types` 覆盖）
3. **矫正按 Label**：手动修改连续变量「均值（标准差）」子行的 Aval → 点「🔧 自动矫正」→ 仅该行被矫正回模板值，其他子行不受位置错位影响
4. **父行 Aval 跟模板**：在「⚙️ 模板配置」改 aval_options[0] → 打开一个分类变量-有子分类 → 父行 Aval radio 显示新值
5. **子行插入**：展开连续变量 → 点子行「＋」→ 在当前子行后出现新空白子行
6. **批量设 Aval**：展开分类变量-有子分类 → 批量设 Aval → 所有子行 Aval 统一更新
7. **静态预览缓存**：反复切换卡片，不卡；修改 dataset 后静态预览内容更新

**Step 2: Push**
```bash
cd d:/shell_tool
git push origin master
```
