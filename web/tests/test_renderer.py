"""renderer.run_preview 单元测试（mock掉 run_render 以隔离R依赖）"""
from unittest.mock import patch
import pandas as pd
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from renderer import run_preview


def _make_card(macvar="PStab", ds="t_demo"):
    return {
        "_id": "abc", "_level": "collapsed",
        "SeqNum": 1, "Section no": "14.1", "table no": "14.1.1",
        "title": "测试", "MacVar": macvar, "Datasets": ds,
        "Trtlab": "A|B", "pop": "FAS",
        "footnote1": "", "footnote2": "", "footnote3": "",
        "footnote4": "", "footnote5": "", "footnote6": "", "footnote7": "",
    }


_MOCK_OK = {
    "status": "success", "output_bytes": b"fake", "elapsed": 0.1,
    "stdout": "", "stderr": "", "error_summary": None, "seq_hint": None,
}

_EMPTY_DS_COLS = ["Class", "Label", "Order", "Aval", "exclude", "BlankCol"]


def test_run_preview_builds_single_entry_yaml():
    """run_preview 应构造只含1条config的YAML并调用run_render。"""
    card = _make_card()
    datasets = {"t_demo": pd.DataFrame(columns=_EMPTY_DS_COLS)}

    with patch("renderer.run_render", return_value=_MOCK_OK) as mock_render:
        result = run_preview(card, datasets)
        assert result["status"] == "success"
        called_yaml = mock_render.call_args[0][0]
        import yaml
        parsed = yaml.safe_load(called_yaml)
        assert len(parsed["config"]) == 1
        assert parsed["config"][0]["SeqNum"] == 1


def test_run_preview_only_passes_relevant_dataset():
    """只传入Datasets字段对应的sheet，过滤掉其他sheet。"""
    card = _make_card(ds="t_demo")
    datasets = {
        "t_demo": pd.DataFrame(columns=_EMPTY_DS_COLS),
        "t_other": pd.DataFrame(columns=_EMPTY_DS_COLS),
    }

    with patch("renderer.run_render", return_value=_MOCK_OK) as mock_render:
        run_preview(card, datasets)
        called_yaml = mock_render.call_args[0][0]
        import yaml
        parsed = yaml.safe_load(called_yaml)
        assert "t_demo" in parsed["datasets"]
        assert "t_other" not in parsed["datasets"]


def test_run_preview_includes_list_for_rptlist():
    """MacVar=RptList 时应同时传入 list sheet。"""
    card = _make_card(macvar="RptList", ds="l_subj")
    datasets = {
        "l_subj": pd.DataFrame(columns=_EMPTY_DS_COLS),
        "list": pd.DataFrame(columns=["ListName", "Byseq", "Byorder", "Lvalable"]),
    }

    with patch("renderer.run_render", return_value=_MOCK_OK) as mock_render:
        run_preview(card, datasets)
        called_yaml = mock_render.call_args[0][0]
        import yaml
        parsed = yaml.safe_load(called_yaml)
        assert "l_subj" in parsed["datasets"]
        assert "list" in parsed["datasets"]
