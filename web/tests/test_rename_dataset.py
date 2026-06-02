"""_apply_rename_dataset 纯函数单元测试。"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd
from datasets_tab import _apply_rename_dataset


def _make_card(ds_name, card_id="c1"):
    return {"_id": card_id, "Datasets": ds_name, "table no": "14.1.1"}


def test_renames_dataset_key():
    datasets = {"t_demo": pd.DataFrame(), "t_other": pd.DataFrame()}
    new_ds, _, _, _ = _apply_rename_dataset(datasets, [], {}, "t_demo", "t_new")
    assert "t_new" in new_ds
    assert "t_demo" not in new_ds
    assert "t_other" in new_ds


def test_original_datasets_not_mutated():
    datasets = {"t_demo": pd.DataFrame()}
    _apply_rename_dataset(datasets, [], {}, "t_demo", "t_new")
    assert "t_demo" in datasets  # 入参未被修改


def test_updates_card_state_datasets_field():
    cards = [_make_card("t_demo", "c1"), _make_card("t_other", "c2")]
    _, new_cs, _, _ = _apply_rename_dataset({"t_demo": pd.DataFrame()}, cards, {}, "t_demo", "t_new")
    assert new_cs[0]["Datasets"] == "t_new"
    assert new_cs[1]["Datasets"] == "t_other"  # 未引用的卡片不受影响


def test_migrates_card_state_session_key():
    from dataset_editor import state_key
    old_key = state_key("t_demo")
    new_key = state_key("t_new")
    ss = {old_key: [{"Label": "Age"}]}
    _, _, add, del_ = _apply_rename_dataset({"t_demo": pd.DataFrame()}, [], ss, "t_demo", "t_new")
    assert new_key in add
    assert add[new_key] == [{"Label": "Age"}]
    assert old_key in del_


def test_migrates_version_session_key():
    ss = {"_ds_version_t_demo": 3}
    _, _, add, del_ = _apply_rename_dataset({"t_demo": pd.DataFrame()}, [], ss, "t_demo", "t_new")
    assert add["_ds_version_t_new"] == 3
    assert "_ds_version_t_demo" in del_


def test_missing_session_keys_not_in_output():
    _, _, add, del_ = _apply_rename_dataset({"t_demo": pd.DataFrame()}, [], {}, "t_demo", "t_new")
    assert add == {}
    assert del_ == []


def test_multiple_cards_all_updated():
    cards = [_make_card("t_demo", f"c{i}") for i in range(3)]
    _, new_cs, _, _ = _apply_rename_dataset({"t_demo": pd.DataFrame()}, cards, {}, "t_demo", "t_new")
    assert all(c["Datasets"] == "t_new" for c in new_cs)
