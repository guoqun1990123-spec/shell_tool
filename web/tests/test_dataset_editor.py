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
