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
