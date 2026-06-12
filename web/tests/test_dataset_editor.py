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


def test_card_state_to_df_preserves_parent_child_grouping():
    """同 Class 有两个父行时，每个父行紧跟自己的子行。"""
    state = [
        {"_id": "p1", "_parent_id": None, "Class": 1, "Order": 0, "Label": "A",
         "Aval": "", "exclude": 0, "BlankCol": "", "Drug": "", "Visit": "", "Base": "",
         "_var_type": "连续变量", "_linked": False, "_expanded": True},
        {"_id": "c1", "_parent_id": "p1", "Class": 1, "Order": 1, "Label": "例数",
         "Aval": "xx", "exclude": 0, "BlankCol": "", "Drug": "", "Visit": "", "Base": "",
         "_var_type": "手动输入", "_linked": True, "_expanded": True},
        {"_id": "p2", "_parent_id": None, "Class": 1, "Order": 0, "Label": "B",
         "Aval": "", "exclude": 0, "BlankCol": "", "Drug": "", "Visit": "", "Base": "",
         "_var_type": "连续变量", "_linked": False, "_expanded": True},
        {"_id": "c2", "_parent_id": "p2", "Class": 1, "Order": 1, "Label": "均值",
         "Aval": "xx.x", "exclude": 0, "BlankCol": "", "Drug": "", "Visit": "", "Base": "",
         "_var_type": "手动输入", "_linked": True, "_expanded": True},
    ]
    df = card_state_to_df(state)
    assert len(df) == 4
    labels = df["Label"].tolist()
    # 每个父行紧跟自己的子行
    assert labels.index("A") < labels.index("例数")
    assert labels.index("B") < labels.index("均值")
    # A 和 A 的子行在 B 之前（同 Class，保留插入顺序）
    assert labels.index("例数") < labels.index("B")


def test_card_state_to_df_strips_any_underscore_key():
    """任意 _ 前缀字段都不出现在输出中。"""
    state = [
        {"Class": 1, "Label": "X", "Order": 0, "Aval": "", "exclude": 0,
         "BlankCol": "", "Drug": "", "Visit": "", "Base": "",
         "_id": "x1", "_var_type": "手动输入", "_parent_id": None,
         "_linked": False, "_expanded": True, "_future_key": "should_not_appear"},
    ]
    df = card_state_to_df(state)
    assert not any(c.startswith("_") for c in df.columns)


def test_df_to_card_state_leading_child_row():
    """Order=1 行在任何 Order=0 行之前时，应被视为独立父行（Order 降为 0）。"""
    df = pd.DataFrame([
        {"Class": 1, "Label": "孤儿行", "Order": 1, "Aval": "xx", "exclude": 0,
         "BlankCol": "", "Drug": "", "Visit": "", "Base": ""},
    ])
    result = df_to_card_state(df)
    assert len(result) == 1
    assert result[0]["_parent_id"] is None


# ── 状态操作函数 ─────────────────────────────────────────────────────────────

from dataset_editor import (
    add_parent_row, delete_row, expand_var_type,
    unlink_child, sync_children_class,
)


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


def _parent_row(id_="p1", class_=1):
    return {
        "_id": id_, "_parent_id": None, "Class": class_, "Order": 0,
        "Label": "A", "Aval": "", "exclude": 0, "BlankCol": "",
        "Drug": "", "Visit": "", "Base": "",
        "_var_type": "手动输入", "_linked": False, "_expanded": True,
    }


def _child_row(id_="c1", parent_id="p1", class_=1):
    return {
        "_id": id_, "_parent_id": parent_id, "Class": class_, "Order": 1,
        "Label": "例数", "Aval": "xx", "exclude": 0, "BlankCol": "",
        "Drug": "", "Visit": "", "Base": "",
        "_var_type": "手动输入", "_linked": True, "_expanded": True,
    }


def test_add_parent_row_gets_next_class():
    state = [_parent_row(class_=2)]
    new_state = add_parent_row(state)
    new_row = new_state[-1]
    assert new_row["Class"] == 3
    assert new_row["Order"] == 0
    assert new_row["_parent_id"] is None
    assert new_row["_linked"] is False


def test_add_parent_row_to_empty_state():
    new_state = add_parent_row([])
    assert len(new_state) == 1
    assert new_state[0]["Class"] == 1


def test_delete_parent_cascades_children():
    state = [_parent_row(), _child_row()]
    new_state = delete_row(state, "p1", cascade=True)
    assert len(new_state) == 0


def test_delete_parent_no_cascade_keeps_child_as_independent():
    state = [_parent_row(), _child_row()]
    new_state = delete_row(state, "p1", cascade=False)
    assert len(new_state) == 1
    assert new_state[0]["_parent_id"] is None
    assert new_state[0]["_linked"] is False


def test_delete_child_directly():
    state = [_parent_row(), _child_row()]
    new_state = delete_row(state, "c1", cascade=True)
    assert len(new_state) == 1
    assert new_state[0]["_id"] == "p1"


def test_expand_var_type_continuous_inserts_children():
    state = [_parent_row()]
    templates = _make_templates()
    new_state = expand_var_type(state, "p1", "连续变量", templates)
    parent = next(r for r in new_state if r["_id"] == "p1")
    children = [r for r in new_state if r.get("_parent_id") == "p1"]
    assert parent["_var_type"] == "连续变量"
    assert len(children) == 2
    assert all(c["_linked"] for c in children)
    assert all(c["Class"] == 1 for c in children)
    assert all(c["Order"] == 1 for c in children)


def test_expand_var_type_replaces_existing_linked_children():
    """切换变量类型时删除旧的 linked 子行，插入新子行。"""
    state = [_parent_row(), _child_row(id_="old_c")]
    # 先切换为连续变量
    templates = _make_templates()
    new_state = expand_var_type(state, "p1", "连续变量", templates)
    children = [r for r in new_state if r.get("_parent_id") == "p1"]
    child_ids = [c["_id"] for c in children]
    assert "old_c" not in child_ids
    assert len(children) == 2


def test_expand_var_type_no_subclass_sets_aval():
    """分类变量-无子分类：父行 Aval 自动填充，不生成子行。"""
    state = [_parent_row()]
    templates = _make_templates()
    new_state = expand_var_type(state, "p1", "分类变量-无子分类", templates)
    parent = next(r for r in new_state if r["_id"] == "p1")
    children = [r for r in new_state if r.get("_parent_id") == "p1"]
    assert parent["Aval"] == "xx (xx.x)"
    assert len(children) == 0


def test_unlink_child():
    state = [_parent_row(), _child_row()]
    new_state = unlink_child(state, "c1")
    child = next(r for r in new_state if r["_id"] == "c1")
    assert child["_linked"] is False
    assert child["_parent_id"] is None


def test_sync_children_class_updates_parent_and_linked_children():
    state = [_parent_row(), _child_row()]
    new_state = sync_children_class(state, "p1", new_class=5)
    parent = next(r for r in new_state if r["_id"] == "p1")
    child = next(r for r in new_state if r["_id"] == "c1")
    assert parent["Class"] == 5
    assert child["Class"] == 5


def test_sync_children_class_does_not_update_unlinked():
    """断链子行（_linked=False）不随父行 Class 同步。"""
    unlinked_child = {**_child_row(), "_linked": False, "_parent_id": None}
    state = [_parent_row(), unlinked_child]
    new_state = sync_children_class(state, "p1", new_class=5)
    # 断链子行 _parent_id=None，不应被更新
    uc = next(r for r in new_state if r["_id"] == "c1")
    assert uc["Class"] == 1  # unchanged


def test_delete_parent_no_cascade_clears_unlinked_child_parent_ref():
    """cascade=False 时，断链子行（_linked=False）的 _parent_id 也应被清除。"""
    unlinked = {**_child_row(id_="cu"), "_linked": False}
    state = [_parent_row(), unlinked]
    new_state = delete_row(state, "p1", cascade=False)
    assert len(new_state) == 1
    assert new_state[0]["_parent_id"] is None
    assert new_state[0]["_linked"] is False


def test_delete_parent_cascade_clears_unlinked_child_parent_ref():
    """cascade=True 时，断链子行不被删除，但 _parent_id 应清除（避免悬空引用）。"""
    unlinked = {**_child_row(id_="cu"), "_linked": False}
    linked = _child_row(id_="cl")
    state = [_parent_row(), unlinked, linked]
    new_state = delete_row(state, "p1", cascade=True)
    # linked 子行被删除，unlinked 子行保留但 _parent_id 清除
    assert len(new_state) == 1
    assert new_state[0]["_id"] == "cu"
    assert new_state[0]["_parent_id"] is None


def test_df_to_card_state_child_inherits_parent_class():
    """子行 Class 为空时应自动继承父行 Class，且父行经 _reindex_class 重编后子行与之一致。"""
    df = pd.DataFrame([
        {"Class": 3, "Label": "年龄", "Order": 0, "Aval": "", "exclude": 0, "BlankCol": "", "Drug": "", "Visit": "", "Base": ""},
        {"Class": "", "Label": "均值", "Order": 1, "Aval": "xx", "exclude": 0, "BlankCol": "", "Drug": "", "Visit": "", "Base": ""},
        {"Class": None, "Label": "中位数", "Order": 1, "Aval": "xx", "exclude": 0, "BlankCol": "", "Drug": "", "Visit": "", "Base": ""},
    ])
    state = df_to_card_state(df)
    assert len(state) == 3
    parent_class = state[0]["Class"]
    assert state[1]["Class"] == parent_class, "空 Class 子行应与父行 Class 一致"
    assert state[2]["Class"] == parent_class, "None Class 子行应与父行 Class 一致"


# ── _infer_var_types / normalize_dataset_state / apply_normalize ────────────
from dataset_editor import _infer_var_types, normalize_dataset_state, apply_normalize, _fill_aval_by_label


def test_infer_var_type_continuous():
    """子行 Aval 全为连续变量模式 → 推断为连续变量。"""
    state = [
        {"_id": "p1", "_parent_id": None, "_linked": False, "_expanded": True,
         "_var_type": "手动输入", "Class": 1, "Order": 0, "Label": "年龄", "Aval": "", "exclude": 0, "BlankCol": ""},
        {"_id": "c1", "_parent_id": "p1", "_linked": True, "_expanded": True,
         "_var_type": "手动输入", "Class": 1, "Order": 1, "Label": "例数", "Aval": "xx", "exclude": 0, "BlankCol": ""},
        {"_id": "c2", "_parent_id": "p1", "_linked": True, "_expanded": True,
         "_var_type": "手动输入", "Class": 1, "Order": 1, "Label": "均值", "Aval": "xx.x (xx.xx)", "exclude": 0, "BlankCol": ""},
    ]
    result = _infer_var_types(state)
    assert result[0]["_var_type"] == "连续变量"


def test_infer_var_type_categorical_no_child():
    """无子行且 Aval 匹配分类模式 → 分类变量-无子分类。"""
    state = [
        {"_id": "p1", "_parent_id": None, "_linked": False, "_expanded": True,
         "_var_type": "手动输入", "Class": 1, "Order": 0, "Label": "性别", "Aval": "xx (xx.x)", "exclude": 0, "BlankCol": ""},
    ]
    result = _infer_var_types(state)
    assert result[0]["_var_type"] == "分类变量-无子分类"


def test_infer_var_type_does_not_overwrite_explicit():
    """已有明确类型的行不被覆盖。"""
    state = [
        {"_id": "p1", "_parent_id": None, "_linked": False, "_expanded": True,
         "_var_type": "日期变量", "Class": 1, "Order": 0, "Label": "日期", "Aval": "", "exclude": 0, "BlankCol": ""},
    ]
    result = _infer_var_types(state)
    assert result[0]["_var_type"] == "日期变量"


def test_normalize_detects_conflicts():
    """Aval 与模板不符时 normalize_dataset_state 应返回 conflicts。"""
    templates = {"连续变量": {"children": [{"Label": "例数", "Aval": "xx"}]}}
    state = [
        {"_id": "p1", "_parent_id": None, "_linked": False, "_expanded": True,
         "_var_type": "连续变量", "Class": 1, "Order": 0, "Label": "年龄", "Aval": "", "exclude": 0, "BlankCol": ""},
        {"_id": "c1", "_parent_id": "p1", "_linked": True, "_expanded": True,
         "_var_type": "手动输入", "Class": 1, "Order": 1, "Label": "例数", "Aval": "N", "exclude": 0, "BlankCol": ""},
    ]
    _, conflicts = normalize_dataset_state(state, templates)
    assert len(conflicts) == 1
    assert conflicts[0]["child_id"] == "c1"
    assert conflicts[0]["template_aval"] == "xx"


def test_apply_normalize_updates_selected():
    """apply_normalize 只更新 selected_ids 中的行。"""
    state = [
        {"_id": "c1", "_parent_id": "p1", "_linked": True, "Aval": "N"},
        {"_id": "c2", "_parent_id": "p1", "_linked": True, "Aval": "old"},
    ]
    conflicts = [
        {"child_id": "c1", "parent_id": "p1", "template_aval": "xx"},
        {"child_id": "c2", "parent_id": "p1", "template_aval": "xx.x"},
    ]
    result = apply_normalize(state, conflicts, selected_ids={"c1"})
    assert result[0]["Aval"] == "xx"
    assert result[1]["Aval"] == "old"


def test_infer_var_type_categorical_pipe_separated():
    """子行 Aval 为 'xx (xx.x)|xx (xx.x)|xx (xx.x)' 格式时应识别为分类变量-有子分类。"""
    state = [
        {"_id": "p1", "_parent_id": None, "_linked": False, "_expanded": True,
         "_var_type": "手动输入", "Class": 1, "Order": 0, "Label": "缓解持续时间，例数(%)", "Aval": "", "exclude": 0, "BlankCol": ""},
        {"_id": "c1", "_parent_id": "p1", "_linked": True, "_expanded": True,
         "_var_type": "手动输入", "Class": 1, "Order": 1, "Label": "<3个月", "Aval": "xx (xx.x)|xx (xx.x)|xx (xx.x)|xx (xx.x)", "exclude": 0, "BlankCol": ""},
        {"_id": "c2", "_parent_id": "p1", "_linked": True, "_expanded": True,
         "_var_type": "手动输入", "Class": 1, "Order": 1, "Label": "3-6个月", "Aval": "xx (xx.x)|xx (xx.x)|xx (xx.x)|xx (xx.x)", "exclude": 0, "BlankCol": ""},
    ]
    result = _infer_var_types(state)
    assert result[0]["_var_type"] == "分类变量-有子分类"


def test_normalize_categorical_pipe_flagged_as_wrong():
    """分类变量-有子分类子行 Aval 为 | 拼接格式时，应提示矫正为单个 xx (xx.x)。"""
    templates = {"分类变量-有子分类": {"children": []}}
    state = [
        {"_id": "p1", "_parent_id": None, "_linked": False, "_expanded": True,
         "_var_type": "分类变量-有子分类", "Class": 1, "Order": 0, "Label": "缓解", "Aval": "", "exclude": 0, "BlankCol": ""},
        {"_id": "c1", "_parent_id": "p1", "_linked": True, "_expanded": True,
         "_var_type": "手动输入", "Class": 1, "Order": 1, "Label": "<3月", "Aval": "xx (xx.x)|xx (xx.x)|xx (xx.x)", "exclude": 0, "BlankCol": ""},
    ]
    _, conflicts = normalize_dataset_state(state, templates)
    assert len(conflicts) == 1
    assert conflicts[0]["template_aval"] == "xx (xx.x)"


def test_normalize_categorical_already_single_correct():
    """分类变量-有子分类子行已是单个 xx (xx.x) 时，不应产生 conflict。"""
    templates = {"分类变量-有子分类": {"children": []}}
    state = [
        {"_id": "p1", "_parent_id": None, "_linked": False, "_expanded": True,
         "_var_type": "分类变量-有子分类", "Class": 1, "Order": 0, "Label": "缓解", "Aval": "", "exclude": 0, "BlankCol": ""},
        {"_id": "c1", "_parent_id": "p1", "_linked": True, "_expanded": True,
         "_var_type": "手动输入", "Class": 1, "Order": 1, "Label": "<3月", "Aval": "xx (xx.x)", "exclude": 0, "BlankCol": ""},
    ]
    _, conflicts = normalize_dataset_state(state, templates)
    assert conflicts == []


def test_normalize_categorical_parent_aval_used_as_expected():
    """父行已选定非默认 Aval（如 xx (xx.x%)）时，矫正期望值应与父行一致而非 aval_options[0]。"""
    templates = {"分类变量-有子分类": {"children": [], "aval_options": ["xx (xx.x)", "xx (xx.x%)"]}}
    state = [
        {"_id": "p1", "_parent_id": None, "_linked": False, "_expanded": True,
         "_var_type": "分类变量-有子分类", "Class": 1, "Order": 0, "Label": "缓解",
         "Aval": "xx (xx.x%)", "exclude": 0, "BlankCol": ""},
        {"_id": "c1", "_parent_id": "p1", "_linked": True, "_expanded": True,
         "_var_type": "手动输入", "Class": 1, "Order": 1, "Label": "完全缓解",
         "Aval": "xx (xx.x)", "exclude": 0, "BlankCol": ""},
    ]
    _, conflicts = normalize_dataset_state(state, templates)
    # 子行 Aval 与父行不符，应报 conflict
    assert len(conflicts) == 1
    assert conflicts[0]["template_aval"] == "xx (xx.x%)"


def test_normalize_categorical_child_matches_parent_aval_no_conflict():
    """子行 Aval 与父行选定值一致时，不应产生 conflict，即使不是 aval_options[0]。"""
    templates = {"分类变量-有子分类": {"children": [], "aval_options": ["xx (xx.x)", "xx (xx.x%)"]}}
    state = [
        {"_id": "p1", "_parent_id": None, "_linked": False, "_expanded": True,
         "_var_type": "分类变量-有子分类", "Class": 1, "Order": 0, "Label": "缓解",
         "Aval": "xx (xx.x%)", "exclude": 0, "BlankCol": ""},
        {"_id": "c1", "_parent_id": "p1", "_linked": True, "_expanded": True,
         "_var_type": "手动输入", "Class": 1, "Order": 1, "Label": "完全缓解",
         "Aval": "xx (xx.x%)", "exclude": 0, "BlankCol": ""},
    ]
    _, conflicts = normalize_dataset_state(state, templates)
    assert conflicts == []


# ── _fill_aval_by_label ──────────────────────────────────────────────────────

def test_fill_aval_by_label_fills_empty_aval():
    """Label='例数' 且 Aval 为空时应自动填充为 'xx'。"""
    state = [{"_id": "c1", "_parent_id": "p1", "_linked": True, "Label": "例数", "Aval": ""}]
    result = _fill_aval_by_label(state)
    assert result[0]["Aval"] == "xx"


def test_fill_aval_by_label_skips_nonempty_aval():
    """Aval 已有值时不覆盖。"""
    state = [{"_id": "c1", "_parent_id": "p1", "_linked": True, "Label": "例数", "Aval": "N"}]
    result = _fill_aval_by_label(state)
    assert result[0]["Aval"] == "N"


def test_fill_aval_by_label_ignores_unknown_label():
    """未知 Label 不受影响。"""
    state = [{"_id": "c1", "_parent_id": "p1", "_linked": True, "Label": "均值", "Aval": ""}]
    result = _fill_aval_by_label(state)
    assert result[0]["Aval"] == ""


def test_df_to_card_state_fills_aval_for_count_row():
    """从 DataFrame 导入时，Label='例数' 且 Aval 为空的行应被自动填充为 'xx'。"""
    df = pd.DataFrame([
        {"Class": 1, "Label": "年龄", "Order": 0, "Aval": "", "exclude": 0,
         "BlankCol": "", "Drug": "", "Visit": "", "Base": ""},
        {"Class": 1, "Label": "例数", "Order": 1, "Aval": "", "exclude": 0,
         "BlankCol": "", "Drug": "", "Visit": "", "Base": ""},
    ])
    result = df_to_card_state(df)
    count_row = next(r for r in result if r["Label"] == "例数")
    assert count_row["Aval"] == "xx"
