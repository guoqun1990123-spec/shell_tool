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
    is_header: bool = False,
) -> dict:
    return {
        "_id": str(uuid.uuid4()),
        "_var_type": var_type,
        "_parent_id": parent_id,
        "_linked": linked,
        "_expanded": expanded,
        "_is_header": is_header,
    }


def _row_data(row: dict) -> dict:
    """提取数据字段（去除 _* 元数据）。"""
    return {k: v for k, v in row.items() if not k.startswith("_")}


def df_to_card_state(df: pd.DataFrame) -> list[dict]:
    """
    DataFrame → card state。
    推断规则：Order=0 行为父行；其后紧随的 Order=1 行为子行（_linked=True）。
    导入后自动推断变量类型、修复 Class 编号。
    """
    if df is None or df.empty:
        return []

    records = df.to_dict(orient="records")
    result: list[dict] = []
    current_parent_id: str | None = None
    current_parent_class: int = 0

    for rec in records:
        order = int(rec.get("Order") or 0)
        if order != 0 and current_parent_id is None:
            order = 0
        data = {col: rec.get(col, "") for col in DATASET_TABLE_COLS}
        data["Order"] = order
        _excl = rec.get("exclude")
        data["exclude"] = int(_excl) if _excl is not None and str(_excl) not in ("", "nan") else 0
        try:
            _cls = rec.get("Class")
            data["Class"] = int(_cls) if _cls is not None and str(_cls) not in ("", "nan") else 0
        except (ValueError, TypeError):
            data["Class"] = 0

        if order == 0:
            meta = _new_meta(var_type=VAR_TYPE_DEFAULT, parent_id=None, linked=False)
            current_parent_id = meta["_id"]
            current_parent_class = data["Class"]
        else:
            meta = _new_meta(var_type=VAR_TYPE_DEFAULT, parent_id=current_parent_id, linked=True)
            if data["Class"] == 0 and current_parent_class:
                data["Class"] = current_parent_class

        result.append({**data, **meta})

    # 修复 Class 编号：按父行出现顺序重编（1, 2, 3...）
    result = _reindex_class(result)

    # 自动推断变量类型
    result = _infer_var_types(result)

    # 推断小节标题行
    result = _infer_is_header(result)

    return result


def card_state_to_df(state: list[dict]) -> pd.DataFrame:
    """
    card state → DataFrame。
    按 state 中出现顺序输出（不再按 Class 排序），每个父行后紧跟其子行。
    断链行（_parent_id=None, Order=1）不写入 DataFrame。
    """
    if not state:
        return pd.DataFrame(columns=DATASET_TABLE_COLS)

    # 按 state 位置顺序取 Order=0 父行（天然排除 Order=1 的断链行）
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


_CONTINUOUS_AVAL_PATTERNS = {
    "xx", "xx.x", "xx.xx", "xx.xxx",
    "xx.x (xx.xx)", "xx.x (xx.x)",
    "xx.xx (xx.xx)", "xx.xx (xx.xxx)",
    "xx – xx", "xx - xx",
    "xx.x – xx.x", "xx.x - xx.x",
    "xx.xx – xx.xx", "xx.xx - xx.xx",
}
_CATEGORICAL_AVAL_PATTERNS = {"xx (xx.x)", "xx (xx.x)%", "xx（xx.x%）"}


def _aval_is_count(aval: str) -> bool:
    """Aval 是纯例数行（所有 | 分段均为 'xx'），推断时跳过此类行。"""
    parts = [p.strip() for p in aval.split("|")]
    return bool(parts) and all(p == "xx" for p in parts)


def _aval_is_categorical(aval: str) -> bool:
    """单个 Aval 值是否符合分类模式（支持 | 分隔的多治疗组格式）。"""
    parts = [p.strip() for p in aval.split("|")]
    return all(p in _CATEGORICAL_AVAL_PATTERNS or p == "" for p in parts) and any(p for p in parts)


def _aval_is_continuous(aval: str) -> bool:
    """单个 Aval 值是否符合连续变量模式（支持 | 分隔）。"""
    parts = [p.strip() for p in aval.split("|")]
    return all(p in _CONTINUOUS_AVAL_PATTERNS or p == "" for p in parts) and any(p for p in parts)


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


def normalize_dataset_state(state: list[dict], templates: dict) -> tuple[list[dict], list[dict]]:
    """
    检查 state 中各父行的 Aval 是否与模板一致。
    返回 (already_ok_state, conflicts)。
    conflicts 是需要用户确认的条目列表，每条为：
      {
        "parent_id": str,
        "parent_label": str,
        "var_type": str,
        "child_id": str | None,   # None 表示父行自身
        "child_label": str,
        "current_aval": str,
        "template_aval": str,
        "apply": bool,            # 用户可勾选
      }
    """
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

        # 父行自身 Aval（无子分类 / 日期变量）
        tmpl_parent_aval = tmpl.get("aval", "")
        if tmpl_parent_aval:
            cur = str(row.get("Aval") or "").strip()
            if cur != tmpl_parent_aval:
                conflicts.append({
                    "parent_id": parent_id,
                    "parent_label": parent_label,
                    "var_type": vtype,
                    "child_id": None,
                    "child_label": f"[父行] {parent_label}",
                    "current_aval": cur,
                    "template_aval": tmpl_parent_aval,
                    "apply": True,
                })

        # 子行 Aval（连续变量 / 分类变量-有子分类 的模板子行）
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

            conflicts.append({
                "parent_id": parent_id,
                "parent_label": parent_label,
                "var_type": vtype,
                "child_id": child["_id"],
                "child_label": str(child.get("Label") or f"子行 {i+1}"),
                "current_aval": cur,
                "template_aval": tmpl_aval,
                "apply": True,
            })

    return state, conflicts


def apply_normalize(state: list[dict], conflicts: list[dict], selected_ids: set[str]) -> list[dict]:
    """将用户选中的 conflict 条目写回 state。"""
    updates: dict[str, str] = {}
    for c in conflicts:
        key = c["child_id"] or c["parent_id"]
        if key in selected_ids:
            updates[key] = c["template_aval"]

    return [
        {**r, "Aval": updates[r["_id"]]} if r["_id"] in updates else r
        for r in state
    ]


def _smart_promote_children(state: list[dict], parent_id: str) -> list[dict]:
    """
    将父行的 linked 子行智能提升：
    - Aval=空 → 新父行（Order=0，独立）
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


def _infer_is_header(state: list[dict]) -> list[dict]:
    """
    推断父行是否为小节标题行：Order=0 + Aval空 + Label非空 + 无 linked 子行 → _is_header=True。
    """
    # 预建有 linked 子行的父行 id 集合，避免 O(n²)
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
            # 只有 Label 非空且 Aval 为空才推断为标题行；Label 也空说明是刚新增的空行
            inferred = (aval == "" and label != "")
            result.append({**row, "_is_header": inferred})
    return result


def _parent_order(state: list[dict]) -> list[dict]:
    """返回所有 Order=0 非标题父行，按当前在 state 中的出现顺序。"""
    return [r for r in state
            if r.get("_parent_id") is None
            and int(r.get("Order") or 0) == 0
            and not r.get("_is_header")]


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
    new_row = _new_data_row(class_val=-1, order=0) | _new_meta()
    new_state = state[:end] + [new_row] + state[end:]
    return _reindex_class(new_state)


# ── Streamlit UI ────────────────────────────────────────────────────────────

def state_key(ds_name: str) -> str:
    return f"card_state_{ds_name}"


def _ensure_card_state(ds_name: str, df, templates: dict) -> list[dict]:
    """确保 session_state 中有该 dataset 的 card state，不存在则从 df 初始化并矫正 Aval。"""
    import streamlit as st
    key = state_key(ds_name)
    if key not in st.session_state:
        state = df_to_card_state(df)
        _, conflicts = normalize_dataset_state(state, templates)
        if conflicts:
            # 只自动填充 Aval 为空的行；非空 Aval 与模板不符时留给用户手动矫正
            _state_map = {r["_id"]: r for r in state}
            selected = {
                c["child_id"] or c["parent_id"]
                for c in conflicts
                if not str(_state_map.get(c["child_id"] or c["parent_id"], {}).get("Aval") or "").strip()
            }
            if selected:
                state = apply_normalize(state, conflicts, selected)
        st.session_state[key] = state
    return st.session_state[key]


def render_dataset_editor(ds_name: str, df, templates: dict):
    """
    渲染卡片式编辑器，返回当前编辑结果（DataFrame）。
    调用方负责将返回值写回 session_state.datasets[ds_name]。
    """
    import streamlit as st
    from templates_io import get_var_types
    VAR_TYPES = get_var_types(templates)

    state = _ensure_card_state(ds_name, df, templates)
    key = state_key(ds_name)

    # ── 全局控制栏 ────────────────────────────────────────────────────────
    col_exp, col_col, col_norm, col_add = st.columns([1, 1, 1.2, 3])
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
    with col_norm:
        if st.button("🔧 自动矫正", key=f"{ds_name}_normalize",
                     help="补全 Class 编号、推断变量类型、自动修正 Aval 为模板标准值"):
            cur = st.session_state[key]
            cur = _reindex_class(cur)
            cur = _infer_is_header(cur)
            cur = _infer_var_types(cur)
            _, conflicts = normalize_dataset_state(cur, templates)
            if conflicts:
                selected = {c["child_id"] or c["parent_id"] for c in conflicts}
                cur = apply_normalize(cur, conflicts, selected)
                st.session_state[key] = cur
                # Clear widget state keys so Streamlit doesn't overwrite normalized Aval
                for c in conflicts:
                    rid = c["child_id"] or c["parent_id"]
                    for wkey in (f"child_aval_{rid}", f"child_aval_sel_{rid}",
                                 f"parent_aval_{rid}", f"unlinked_aval_{rid}"):
                        if wkey in st.session_state:
                            del st.session_state[wkey]
                labels = list(dict.fromkeys(c["parent_label"] for c in conflicts))
                summary = "、".join(labels[:3]) + ("…" if len(labels) > 3 else "")
                st.toast(f"✅ 已矫正 {len(conflicts)} 处 Aval（{summary}）")
            else:
                st.session_state[key] = cur
                st.toast("✅ 已自动矫正 Class 编号和变量类型，Aval 均已符合模板")
            st.rerun()
    with col_add:
        if st.button("＋ 添加变量行", key=f"{ds_name}_add_row", type="secondary"):
            st.session_state[key] = add_parent_row(st.session_state[key])
            st.rerun()

    state = st.session_state[key]

    # 计算父行列表（用于边界判断）
    parent_ids = [r["_id"] for r in state if r.get("_parent_id") is None and int(r.get("Order") or 0) == 0]

    for row in state:
        if row.get("_parent_id") is not None or int(row.get("Order") or 0) != 0:
            continue  # 子行在父行处理中渲染

        row_id = row["_id"]
        is_expanded = row.get("_expanded", True)
        is_header = row.get("_is_header", False)
        linked_children = [r for r in state if r.get("_parent_id") == row_id and r.get("_linked")]
        p_idx = parent_ids.index(row_id) if row_id in parent_ids else 0
        is_first = p_idx == 0
        is_last = p_idx == len(parent_ids) - 1

        # ── 父行卡片 ──────────────────────────────────────────────────
        # header 行注入浅蓝灰底色
        if is_header:
            st.markdown(
                f"""<style>
                div[data-testid="stVerticalBlock"]:has(> div > div button[kind="primary"][title="切换为小节标题行"][key="{ds_name}_hdr_{row_id}"]) {{
                    background-color: #eef2ff;
                    border-radius: 6px;
                }}
                </style>""",
                unsafe_allow_html=True,
            )

        with st.container(border=True):
            if is_header:
                # header 行：toggle(折叠无意义隐去)、上/下移、插入后、📌、label、删除
                c_up, c_down, c_ins, c_hdr, c_label, c_del = st.columns([0.4, 0.4, 0.4, 0.4, 5.5, 0.4])
            else:
                c_toggle, c_up, c_down, c_ins, c_hdr, c_class, c_label, c_type, c_aval, c_del = st.columns(
                    [0.4, 0.4, 0.4, 0.4, 0.4, 0.8, 3.5, 2, 1.5, 0.4]
                )
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

            with c_hdr:
                hdr_btn_type = "primary" if is_header else "secondary"
                if st.button("📌", key=f"{ds_name}_hdr_{row_id}", type=hdr_btn_type, help="切换为小节标题行"):
                    if not is_header and linked_children:
                        # 有子行时切换为 header 需确认
                        st.session_state[f"confirm_to_header_{row_id}"] = True
                        st.rerun()
                    else:
                        st.session_state[key] = [
                            {**r, "_is_header": not is_header} if r["_id"] == row_id else r
                            for r in st.session_state[key]
                        ]
                        st.rerun()

            if not is_header:
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

            if not is_header:
                with c_type:
                    cur_type = row.get("_var_type", "手动输入")
                    new_type = st.selectbox(
                        "类型", options=VAR_TYPES,
                        index=VAR_TYPES.index(cur_type) if cur_type in VAR_TYPES else 0,
                        label_visibility="collapsed",
                        key=f"vartype_{row_id}"
                    )
                    if new_type != cur_type:
                        pending_sub_key = f"pending_subclass_{row_id}"
                        if pending_sub_key in st.session_state:
                            del st.session_state[pending_sub_key]
                        if linked_children and new_type != VAR_TYPE_DEFAULT:
                            # 有现有子行且新类型非手动输入 → 询问处理方式
                            # 不调 st.rerun()，确认框在同一轮渲染里直接出现，避免无限 rerun
                            st.session_state[f"pending_vartype_{row_id}"] = new_type
                        else:
                            st.session_state[key] = expand_var_type(
                                st.session_state[key], row_id, new_type, templates
                            )
                            if new_type == "分类变量-有子分类":
                                st.session_state[pending_sub_key] = ""
                            st.rerun()

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
                        if new_aval_val != cur_aval:
                            st.session_state[key] = [
                                {**r, "Aval": new_aval_val} if r["_id"] == row_id else r
                                for r in st.session_state[key]
                            ]

            with c_del:
                if st.button("🗑", key=f"del_{row_id}", help="删除此变量行"):
                    if linked_children:
                        st.session_state[f"confirm_del_{row_id}"] = True
                        st.rerun()
                    else:
                        st.session_state[key] = delete_row(st.session_state[key], row_id, cascade=True)
                        st.rerun()

        # ── 变量类型切换确认（有现有子行时）──────────────────────────
        pending_vt_key = f"pending_vartype_{row_id}"
        if pending_vt_key in st.session_state:
            new_vt = st.session_state[pending_vt_key]
            st.info(f"切换为「{new_vt}」，当前有 {len(linked_children)} 个子行，请选择处理方式：")
            col_replace, col_keep, col_vt_cancel = st.columns(3)
            with col_replace:
                if st.button("替换为模板子行", key=f"vt_replace_{row_id}"):
                    st.session_state[key] = expand_var_type(
                        st.session_state[key], row_id, new_vt, templates
                    )
                    if new_vt == "分类变量-有子分类":
                        st.session_state[f"pending_subclass_{row_id}"] = ""
                    del st.session_state[pending_vt_key]
                    st.rerun()
            with col_keep:
                if st.button("保留现有子行", key=f"vt_keep_{row_id}"):
                    st.session_state[key] = [
                        {**r, "_var_type": new_vt} if r["_id"] == row_id else r
                        for r in st.session_state[key]
                    ]
                    del st.session_state[pending_vt_key]
                    # 重置 selectbox 显示为新类型
                    if f"vartype_{row_id}" in st.session_state:
                        del st.session_state[f"vartype_{row_id}"]
                    st.rerun()
            with col_vt_cancel:
                if st.button("取消", key=f"vt_cancel_{row_id}"):
                    del st.session_state[pending_vt_key]
                    # 重置 selectbox 回旧类型
                    if f"vartype_{row_id}" in st.session_state:
                        del st.session_state[f"vartype_{row_id}"]
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
            subclass_text = st.text_area(
                "子分类列表",
                value=st.session_state[pending_sub_key],
                placeholder="例：\n男\n女",
                key=f"subclass_input_{row_id}",
                label_visibility="collapsed",
                height=120,
            )
            st.session_state[pending_sub_key] = subclass_text
            col_ok, col_cancel = st.columns(2)
            with col_ok:
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

        # ── 切换为 header 确认（有子行时）────────────────────────────
        confirm_to_header_key = f"confirm_to_header_{row_id}"
        if confirm_to_header_key in st.session_state:
            st.warning(f"变量「{row.get('Label')}」有 {len(linked_children)} 个子行，请选择处理方式：")
            col_del, col_promote, col_cancel = st.columns(3)
            with col_del:
                if st.button("删除子行", key=f"to_hdr_del_{row_id}"):
                    new_state = [
                        r for r in st.session_state[key]
                        if not (r.get("_parent_id") == row_id and r.get("_linked"))
                    ]
                    new_state = [
                        {**r, "_is_header": True, "_var_type": VAR_TYPE_DEFAULT, "Aval": ""}
                        if r["_id"] == row_id else r
                        for r in new_state
                    ]
                    del st.session_state[confirm_to_header_key]
                    st.session_state[key] = _reindex_class(new_state)
                    st.rerun()
            with col_promote:
                if st.button("子行转为父行", key=f"to_hdr_promote_{row_id}"):
                    cur = st.session_state[key]
                    promoted = _smart_promote_children(cur, row_id)
                    # 移除旧子行，将父行设为 header
                    new_state = [
                        r for r in cur
                        if not (r.get("_parent_id") == row_id and r.get("_linked"))
                    ]
                    new_state = [
                        {**r, "_is_header": True, "_var_type": VAR_TYPE_DEFAULT, "Aval": ""}
                        if r["_id"] == row_id else r
                        for r in new_state
                    ]
                    # 将智能提升的行插入父行之后
                    parent_pos = next(i for i, r in enumerate(new_state) if r["_id"] == row_id)
                    new_state = new_state[:parent_pos + 1] + promoted + new_state[parent_pos + 1:]
                    del st.session_state[confirm_to_header_key]
                    st.session_state[key] = _reindex_class(new_state)
                    st.rerun()
            with col_cancel:
                if st.button("取消", key=f"to_hdr_cancel_{row_id}"):
                    del st.session_state[confirm_to_header_key]
                    st.rerun()

        # ── 子行渲染（仅展开时，header 行无子行不渲染）──────────────
        if is_expanded and not is_header:
            with st.expander("更多字段 ▼", expanded=False):
                ef1, ef2, ef3, ef4, ef5 = st.columns(5)
                cur_excl = int(row.get("exclude") or 0)
                new_excl = ef1.selectbox(
                    "exclude", options=[0, 1], index=cur_excl,
                    format_func=lambda x: "显示" if x == 0 else "隐藏",
                    key=f"excl_{row_id}",
                )
                if new_excl != cur_excl:
                    st.session_state[key] = [
                        {**r, "exclude": new_excl} if r["_id"] == row_id else r
                        for r in st.session_state[key]
                    ]
                    st.rerun()
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
                cur_drug = str(row.get("Drug") or "")
                new_drug = ef3.text_input("Drug", value=cur_drug,
                                          key=f"drug_{row_id}")
                if new_drug != cur_drug:
                    st.session_state[key] = [
                        {**r, "Drug": new_drug} if r["_id"] == row_id else r
                        for r in st.session_state[key]
                    ]
                    st.rerun()
                cur_visit = str(row.get("Visit") or "")
                new_visit = ef4.text_input("Visit", value=cur_visit,
                                           key=f"visit_{row_id}")
                if new_visit != cur_visit:
                    st.session_state[key] = [
                        {**r, "Visit": new_visit} if r["_id"] == row_id else r
                        for r in st.session_state[key]
                    ]
                    st.rerun()
                cur_base = str(row.get("Base") or "")
                new_base = ef5.text_input("Base", value=cur_base,
                                          key=f"base_{row_id}")
                if new_base != cur_base:
                    st.session_state[key] = [
                        {**r, "Base": new_base} if r["_id"] == row_id else r
                        for r in st.session_state[key]
                    ]
                    st.rerun()
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
                            st.rerun()
                    with cc_aval:
                        parent_vtype = row.get("_var_type", VAR_TYPE_DEFAULT)
                        aval_opts_for_child = templates.get(parent_vtype, {}).get("aval_options", [])
                        cur_child_aval = str(child.get("Aval") or "")
                        if aval_opts_for_child:
                            _CUSTOM = "✏️ 自定义"
                            dropdown_opts = aval_opts_for_child + [_CUSTOM]
                            sel_idx = (
                                aval_opts_for_child.index(cur_child_aval)
                                if cur_child_aval in aval_opts_for_child
                                else len(aval_opts_for_child)  # 指向 _CUSTOM
                            )
                            sel = st.selectbox(
                                "Aval", options=dropdown_opts, index=sel_idx,
                                label_visibility="collapsed",
                                key=f"child_aval_sel_{child_id}"
                            )
                            if sel == _CUSTOM:
                                new_aval = st.text_input(
                                    "自定义 Aval", value=cur_child_aval,
                                    label_visibility="collapsed",
                                    key=f"child_aval_{child_id}"
                                )
                            else:
                                new_aval = sel
                                # 清除可能残留的自定义输入 key
                                if f"child_aval_{child_id}" in st.session_state:
                                    del st.session_state[f"child_aval_{child_id}"]
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
        cls = int(row.get("Class") or 0)
        st.warning(f"⚠️ 断链行（原 Class={cls}）：此行已与父行断开，请重新分配或删除。")
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
