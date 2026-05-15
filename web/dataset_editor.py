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
