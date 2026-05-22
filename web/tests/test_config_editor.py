"""config_editor 纯函数单元测试（不依赖 Streamlit）。"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config_editor import (
    _empty_card, df_to_card_state, card_state_to_df,
    _compute_table_nos, _update_card, _delete_card,
    _copy_card, _move_card, _insert_after,
)
import pandas as pd


def test_empty_card_defaults():
    card = _empty_card()
    assert card["_level"] == "collapsed"
    assert card["_tableno_overridden"] is False
    assert card["_title_overridden"] is False
    assert "_id" in card


def test_compute_table_nos_basic():
    cards = [
        {**_empty_card(), "Section no": "14.1", "cat": "表"},
        {**_empty_card(), "Section no": "14.1", "cat": "表"},
        {**_empty_card(), "Section no": "14.2", "cat": "表"},
    ]
    result = _compute_table_nos(cards)
    assert result[0]["table no"] == "14.1.1.1"
    assert result[1]["table no"] == "14.1.2.1"
    assert result[2]["table no"] == "14.2.1.1"


def test_compute_table_nos_listing_uses_16_2():
    cards = [
        {**_empty_card(), "Section no": "14.1", "cat": "列表"},
    ]
    result = _compute_table_nos(cards)
    assert result[0]["table no"].startswith("16.2.")


def test_update_card_changes_field():
    cards = [_empty_card()]
    card_id = cards[0]["_id"]
    result = _update_card(cards, card_id, title="新标题")
    assert result[0]["title"] == "新标题"


def test_delete_card_removes_it():
    cards = [_empty_card(), _empty_card()]
    card_id = cards[0]["_id"]
    result = _delete_card(cards, card_id)
    assert len(result) == 1
    assert result[0]["_id"] != card_id


def test_copy_card_inserts_after():
    cards = [_empty_card(), _empty_card()]
    original_id = cards[0]["_id"]
    result = _copy_card(cards, original_id)
    assert len(result) == 3
    assert result[0]["_id"] == original_id
    assert result[1]["_id"] != original_id   # 副本紧随其后
    assert result[1]["_level"] == "collapsed"


def test_move_card_up():
    cards = [_empty_card(), _empty_card()]
    id0, id1 = cards[0]["_id"], cards[1]["_id"]
    result = _move_card(cards, 1, -1)
    assert result[0]["_id"] == id1
    assert result[1]["_id"] == id0


def test_insert_after():
    cards = [_empty_card()]
    original_id = cards[0]["_id"]
    result = _insert_after(cards, original_id)
    assert len(result) == 2
    assert result[0]["_id"] == original_id


def test_card_state_to_df_seqnum():
    cards = [_empty_card(), _empty_card()]
    df = card_state_to_df(cards)
    assert list(df["SeqNum"]) == [1, 2]


def test_df_to_card_state_roundtrip():
    cards = [_empty_card()]
    cards[0]["title"] = "测试"
    cards[0]["Section no"] = "14.1"
    df = card_state_to_df(cards)
    restored = df_to_card_state(df)
    assert restored[0]["title"] == "测试"
    assert restored[0]["Section no"] == "14.1"
    assert restored[0]["_level"] == "collapsed"
