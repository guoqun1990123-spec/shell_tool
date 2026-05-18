"""卡片式 Datasets 编辑器。

公开接口：
  df_to_card_state(df)          DataFrame → list[dict]（含 _* 元数据）
  card_state_to_df(state)       list[dict] → DataFrame（去除 _* 元数据）
  get_next_class(state)         计算新父行应得的 Class 值
  render_dataset_editor(...)    Streamlit UI 组件（后续实现）
"""
import uuid
import pandas as pd

from schema import DATASET_TABLE_COLS, VAR_TYPE_DEFAULT

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
    return {k: v for k, v in row.items() if not k.startswith("_")}


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
        if order != 0 and current_parent_id is None:
            # Leading child row with no parent yet — treat as independent parent
            order = 0
        data = {col: rec.get(col, "") for col in DATASET_TABLE_COLS}
        data["Order"] = order
        data["exclude"] = int(rec.get("exclude") or 0)
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
    父行按 Class 排序，每个父行后紧跟其子行（按 Order 排序）。
    折叠状态子行仍保留。
    """
    if not state:
        return pd.DataFrame(columns=DATASET_TABLE_COLS)

    # 父行按 Class 排序（稳定排序保留同 Class 的插入顺序）
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
    cascade=True：同时删除所有 _linked=True 的子行；_linked=False 的子行清除 _parent_id 引用。
    cascade=False：所有子行（无论是否 linked）的 _parent_id 置 None、_linked=False，变为独立行。
    """
    new_state = []
    for r in state:
        if r["_id"] == row_id:
            continue
        if r.get("_parent_id") == row_id:
            if cascade and r.get("_linked"):
                continue  # 级联删除 linked 子行
            # cascade=True 的 unlinked 子行，或 cascade=False 的任意子行：清除 parent 引用
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
    3. 更新父行 _var_type 和 Aval（若模板有 aval 字段）
    """
    parent = next((r for r in state if r["_id"] == parent_id), None)
    if parent is None:
        return state

    cls = parent.get("Class", 0)
    tmpl = templates.get(new_var_type, {})

    # 删除旧 linked 子行
    new_state = [r for r in state if not (r.get("_parent_id") == parent_id and r.get("_linked"))]

    # 更新父行
    new_state = [
        {**r, "_var_type": new_var_type, "Aval": tmpl.get("aval", r.get("Aval", ""))}
        if r["_id"] == parent_id else r
        for r in new_state
    ]

    # 在父行之后插入子行
    parent_idx = next(i for i, r in enumerate(new_state) if r["_id"] == parent_id)
    children = []
    for child_tmpl in tmpl.get("children", []):
        child_data = _new_data_row(class_val=cls, order=1) | child_tmpl
        child_meta = _new_meta(parent_id=parent_id, linked=True)
        children.append({**child_data, **child_meta})

    return new_state[:parent_idx + 1] + children + new_state[parent_idx + 1:]


def unlink_child(state: list[dict], child_id: str) -> list[dict]:
    """断开子行链接：_linked=False，_parent_id=None，使其变为独立行。"""
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


def _parent_order(state: list[dict]) -> list[dict]:
    """返回所有 Order=0 父行，按当前在 state 中的出现顺序。"""
    return [r for r in state if r.get("_parent_id") is None and int(r.get("Order") or 0) == 0]


def _reindex_class(state: list[dict]) -> list[dict]:
    """
    按父行在 state 中的顺序重新分配 Class（从 1 递增），
    同步更新每个父行的 linked 子行 Class，断链行 Class 不变。
    """
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


def _group_slice(state: list[dict], parent_id: str) -> tuple[int, int]:
    """
    返回 (start, end) 使 state[start:end] 包含父行及其所有 linked 子行。
    断链行（_linked=False）不含在内。
    """
    start = next(i for i, r in enumerate(state) if r["_id"] == parent_id)
    end = start + 1
    while end < len(state):
        r = state[end]
        if r.get("_parent_id") == parent_id and r.get("_linked"):
            end += 1
        else:
            break
    return start, end


def move_parent(state: list[dict], parent_id: str, direction: int) -> list[dict]:
    """
    将父行（及其 linked 子行）整体上移（direction=-1）或下移（direction=1）一位。
    断链行不跟随移动。移动后按新顺序重排 Class。
    """
    parents = _parent_order(state)
    idx = next((i for i, p in enumerate(parents) if p["_id"] == parent_id), None)
    if idx is None:
        return state
    target_idx = idx + direction
    if target_idx < 0 or target_idx >= len(parents):
        return state

    # 找到要交换的邻居
    neighbor_id = parents[target_idx]["_id"]

    # 切出两个 group 的 slice
    s1, e1 = _group_slice(state, parent_id)
    s2, e2 = _group_slice(state, neighbor_id)

    group_self = state[s1:e1]
    group_neighbor = state[s2:e2]

    # 重组：把两段交换
    if direction == -1:
        # self 在 neighbor 之后，上移 → neighbor 先
        before = state[:s2]
        after = state[e1:]
        new_state = before + group_self + group_neighbor + after
    else:
        # self 在 neighbor 之前，下移 → neighbor 先
        before = state[:s1]
        after = state[e2:]
        new_state = before + group_neighbor + group_self + after

    return _reindex_class(new_state)


def insert_after(state: list[dict], parent_id: str) -> list[dict]:
    """
    在指定父行（及其 linked 子行）之后插入一个新空白父行。
    新行 Class 由移动后 _reindex_class 自动分配，此处先用占位值 0。
    """
    _, end = _group_slice(state, parent_id)
    new_row = _new_data_row(class_val=0, order=0) | _new_meta()
    new_state = state[:end] + [new_row] + state[end:]
    return _reindex_class(new_state)


# ── Streamlit UI ────────────────────────────────────────────────────────────

def state_key(ds_name: str) -> str:
    return f"card_state_{ds_name}"


def _ensure_card_state(ds_name: str, df) -> list[dict]:
    """确保 session_state 中有该 dataset 的 card state，不存在则从 df 初始化。"""
    import streamlit as st
    key = state_key(ds_name)
    if key not in st.session_state:
        st.session_state[key] = df_to_card_state(df)
    return st.session_state[key]


def render_dataset_editor(ds_name: str, df, templates: dict):
    """
    渲染卡片式编辑器，返回当前编辑结果（DataFrame）。
    调用方负责将返回值写回 session_state.datasets[ds_name]。
    """
    import streamlit as st
    from schema import VAR_TYPES

    state = _ensure_card_state(ds_name, df)
    key = state_key(ds_name)

    # ── 全局控制栏 ────────────────────────────────────────────────────────
    col_exp, col_col, col_add = st.columns([1, 1, 3])
    with col_exp:
        if st.button("展开全部", key=f"{ds_name}_expand_all"):
            st.session_state[key] = [{**r, "_expanded": True} for r in st.session_state[key]]
            st.rerun()
    with col_col:
        if st.button("折叠全部", key=f"{ds_name}_collapse_all"):
            st.session_state[key] = [
                {**r, "_expanded": False} if r.get("_parent_id") is None else r
                for r in st.session_state[key]
            ]
            st.rerun()
    with col_add:
        if st.button("＋ 添加变量行", key=f"{ds_name}_add_row", type="secondary"):
            st.session_state[key] = add_parent_row(st.session_state[key])
            st.rerun()

    state = st.session_state[key]

    # ── 行渲染 ────────────────────────────────────────────────────────────
    # 计算父行列表（用于边界判断）
    parent_ids = [r["_id"] for r in state if r.get("_parent_id") is None and int(r.get("Order") or 0) == 0]

    for row in state:
        if row.get("_parent_id") is not None or int(row.get("Order") or 0) != 0:
            continue  # 子行在父行处理中渲染

        row_id = row["_id"]
        is_expanded = row.get("_expanded", True)
        linked_children = [r for r in state if r.get("_parent_id") == row_id and r.get("_linked")]
        p_idx = parent_ids.index(row_id) if row_id in parent_ids else 0
        is_first = p_idx == 0
        is_last = p_idx == len(parent_ids) - 1

        # ── 父行卡片 ──────────────────────────────────────────────────
        with st.container(border=True):
            c_toggle, c_up, c_down, c_ins, c_class, c_label, c_type, c_del = st.columns([0.4, 0.4, 0.4, 0.4, 0.8, 4, 2, 0.4])

            with c_toggle:
                toggle_label = "⊟" if is_expanded else "⊞"
                if st.button(toggle_label, key=f"toggle_{row_id}", help="展开/折叠"):
                    st.session_state[key] = [
                        {**r, "_expanded": not r["_expanded"]} if r["_id"] == row_id else r
                        for r in st.session_state[key]
                    ]
                    st.rerun()

            with c_up:
                if st.button("▲", key=f"up_{row_id}", disabled=is_first, help="上移"):
                    st.session_state[key] = move_parent(st.session_state[key], row_id, -1)
                    st.rerun()

            with c_down:
                if st.button("▼", key=f"down_{row_id}", disabled=is_last, help="下移"):
                    st.session_state[key] = move_parent(st.session_state[key], row_id, 1)
                    st.rerun()

            with c_ins:
                if st.button("＋", key=f"ins_{row_id}", help="在此后插入变量行"):
                    st.session_state[key] = insert_after(st.session_state[key], row_id)
                    st.rerun()

            with c_class:
                new_class = st.number_input(
                    "Class", value=int(row.get("Class") or 0),
                    step=1, min_value=0, label_visibility="collapsed",
                    key=f"class_{row_id}"
                )
                if new_class != int(row.get("Class") or 0):
                    if linked_children:
                        st.session_state[f"pending_class_{row_id}"] = new_class
                    else:
                        st.session_state[key] = [
                            {**r, "Class": new_class} if r["_id"] == row_id else r
                            for r in st.session_state[key]
                        ]

            with c_label:
                new_label = st.text_input(
                    "Label", value=str(row.get("Label") or ""),
                    placeholder="变量名称", label_visibility="collapsed",
                    key=f"label_{row_id}"
                )
                if new_label != str(row.get("Label") or ""):
                    st.session_state[key] = [
                        {**r, "Label": new_label} if r["_id"] == row_id else r
                        for r in st.session_state[key]
                    ]

            with c_type:
                cur_type = row.get("_var_type", "手动输入")
                new_type = st.selectbox(
                    "类型", options=VAR_TYPES,
                    index=VAR_TYPES.index(cur_type) if cur_type in VAR_TYPES else 0,
                    label_visibility="collapsed",
                    key=f"vartype_{row_id}"
                )
                if new_type != cur_type:
                    # 切换离开时清除旧的子分类输入
                    pending_sub_key = f"pending_subclass_{row_id}"
                    if pending_sub_key in st.session_state:
                        del st.session_state[pending_sub_key]
                    st.session_state[key] = expand_var_type(
                        st.session_state[key], row_id, new_type, templates
                    )
                    if new_type == "分类变量-有子分类":
                        st.session_state[pending_sub_key] = ""
                    st.rerun()

            with c_del:
                if st.button("🗑", key=f"del_{row_id}", help="删除此变量行"):
                    if linked_children:
                        st.session_state[f"confirm_del_{row_id}"] = True
                        st.rerun()
                    else:
                        st.session_state[key] = delete_row(st.session_state[key], row_id, cascade=True)
                        st.rerun()

        # ── Class 修改确认 ────────────────────────────────────────────
        pending_class_key = f"pending_class_{row_id}"
        if pending_class_key in st.session_state:
            new_cls = st.session_state[pending_class_key]
            st.warning(f"变量「{row.get('Label')}」有 {len(linked_children)} 个子行，是否同步修改 Class → {new_cls}？")
            col_y, col_n = st.columns(2)
            with col_y:
                if st.button("是，同步子行", key=f"cls_yes_{row_id}"):
                    st.session_state[key] = sync_children_class(st.session_state[key], row_id, new_cls)
                    del st.session_state[pending_class_key]
                    st.rerun()
            with col_n:
                if st.button("否，仅当前行", key=f"cls_no_{row_id}"):
                    st.session_state[key] = [
                        {**r, "Class": new_cls} if r["_id"] == row_id else r
                        for r in st.session_state[key]
                    ]
                    del st.session_state[pending_class_key]
                    st.rerun()

        # ── 删除确认 ─────────────────────────────────────────────────
        confirm_del_key = f"confirm_del_{row_id}"
        if confirm_del_key in st.session_state:
            st.warning(f"变量「{row.get('Label')}」有 {len(linked_children)} 个子行，是否一并删除？")
            col_y, col_n = st.columns(2)
            with col_y:
                if st.button("是，级联删除", key=f"del_yes_{row_id}"):
                    st.session_state[key] = delete_row(st.session_state[key], row_id, cascade=True)
                    del st.session_state[confirm_del_key]
                    st.rerun()
            with col_n:
                if st.button("否，保留子行", key=f"del_no_{row_id}"):
                    st.session_state[key] = delete_row(st.session_state[key], row_id, cascade=False)
                    del st.session_state[confirm_del_key]
                    st.rerun()

        # ── 子分类输入框（分类变量-有子分类，等待用户确认）────────────
        pending_sub_key = f"pending_subclass_{row_id}"
        if pending_sub_key in st.session_state:
            st.info(f"请输入「{row.get('Label', '')}」的子分类，每行一个：")
            sc_col_text, sc_col_aval = st.columns([3, 1])
            with sc_col_text:
                subclass_text = st.text_area(
                    "子分类列表",
                    value=st.session_state[pending_sub_key],
                    placeholder="例：\n男\n女",
                    key=f"subclass_input_{row_id}",
                    label_visibility="collapsed",
                    height=120,
                )
                st.session_state[pending_sub_key] = subclass_text
            with sc_col_aval:
                st.caption("子行 Aval 默认值")
                default_aval = st.radio(
                    "Aval",
                    options=["空", "xx (xx.x)"],
                    index=0,
                    key=f"subclass_aval_{row_id}",
                    label_visibility="collapsed",
                )
            col_ok, col_cancel = st.columns(2)
            with col_ok:
                if st.button("确认生成子行", key=f"subclass_ok_{row_id}", type="primary"):
                    names = [n.strip() for n in subclass_text.splitlines() if n.strip()]
                    cls = row.get("Class", 0)
                    aval_val = "" if default_aval == "空" else "xx (xx.x)"
                    new_children = []
                    for name in names:
                        child_data = _new_data_row(class_val=cls, order=1)
                        child_data["Label"] = name
                        child_data["Aval"] = aval_val
                        child_meta = _new_meta(parent_id=row_id, linked=True)
                        new_children.append({**child_data, **child_meta})
                    cur_state = st.session_state[key]
                    parent_idx = next(i for i, r in enumerate(cur_state) if r["_id"] == row_id)
                    st.session_state[key] = cur_state[:parent_idx + 1] + new_children + cur_state[parent_idx + 1:]
                    del st.session_state[pending_sub_key]
                    st.rerun()
            with col_cancel:
                if st.button("取消", key=f"subclass_cancel_{row_id}"):
                    del st.session_state[pending_sub_key]
                    st.rerun()

        # ── 子行渲染（仅展开时）──────────────────────────────────────
        if is_expanded:
            for child in linked_children:
                child_id = child["_id"]
                with st.container():
                    cc_link, cc_class, cc_label, cc_aval, cc_unlink = st.columns([0.4, 1, 3, 3, 1.5])
                    with cc_link:
                        st.markdown("🔗")
                    with cc_class:
                        st.text_input(
                            "Class", value=str(child.get("Class") or ""),
                            disabled=True, label_visibility="collapsed",
                            key=f"child_class_{child_id}"
                        )
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
                    with cc_aval:
                        new_aval = st.text_input(
                            "Aval", value=str(child.get("Aval") or ""),
                            label_visibility="collapsed",
                            key=f"child_aval_{child_id}"
                        )
                        if new_aval != str(child.get("Aval") or ""):
                            st.session_state[key] = [
                                {**r, "Aval": new_aval} if r["_id"] == child_id else r
                                for r in st.session_state[key]
                            ]
                    with cc_unlink:
                        if st.button("断开链接", key=f"unlink_{child_id}"):
                            st.session_state[key] = unlink_child(st.session_state[key], child_id)
                            st.rerun()

    # ── 断链独立行渲染（_parent_id=None 但 _linked 已为 False 的原子行）────
    for row in st.session_state[key]:
        if row.get("_parent_id") is not None:
            continue
        if int(row.get("Order") or 0) != 1:
            continue
        # 断链的 Order=1 行：作为独立行渲染
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
                    st.session_state[key] = [
                        {**r, "Class": new_class} if r["_id"] == row_id else r
                        for r in st.session_state[key]
                    ]
            with cl:
                new_label = st.text_input(
                    "Label", value=str(row.get("Label") or ""),
                    label_visibility="collapsed", key=f"unlinked_label_{row_id}"
                )
                if new_label != str(row.get("Label") or ""):
                    st.session_state[key] = [
                        {**r, "Label": new_label} if r["_id"] == row_id else r
                        for r in st.session_state[key]
                    ]
            with ca:
                new_aval = st.text_input(
                    "Aval", value=str(row.get("Aval") or ""),
                    label_visibility="collapsed", key=f"unlinked_aval_{row_id}"
                )
                if new_aval != str(row.get("Aval") or ""):
                    st.session_state[key] = [
                        {**r, "Aval": new_aval} if r["_id"] == row_id else r
                        for r in st.session_state[key]
                    ]
            with cd:
                if st.button("🗑", key=f"del_unlinked_{row_id}"):
                    st.session_state[key] = delete_row(st.session_state[key], row_id, cascade=False)
                    st.rerun()

    return card_state_to_df(st.session_state[key])
