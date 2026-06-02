"""renderer 单元测试（run_preview + _parse_r_error）"""
from unittest.mock import patch
import pandas as pd
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from renderer import run_preview, _parse_r_error


# ── _parse_r_error 测试 ───────────────────────────────────────────────────────

def test_parse_error_extracts_error_in_line():
    log = "some preamble\nError in generate_table(cfg) : object 'x' not found\nTraceback..."
    summary, seq = _parse_r_error(log)
    assert "Error in generate_table" in summary
    assert seq is None


def test_parse_error_extracts_seqnum():
    log = "Processing SeqNum=3\nError in foo() : bad value"
    summary, seq = _parse_r_error(log)
    assert seq == 3


def test_parse_error_seqnum_case_variants():
    for pattern in ["Seq 5", "seqnum: 5", "SeqNum=5", "seq=5"]:
        _, seq = _parse_r_error(pattern)
        assert seq == 5, f"failed for pattern: {pattern!r}"


def test_parse_error_fallback_to_last_line():
    log = "line1\nline2\nfinal error message"
    summary, seq = _parse_r_error(log)
    assert summary == "final error message"
    assert seq is None


def test_parse_error_empty_log():
    summary, seq = _parse_r_error("")
    assert summary == "未知错误"
    assert seq is None


def test_parse_error_stop_call_detected():
    log = 'stop("invalid MacVar: FooBar")'
    summary, _ = _parse_r_error(log)
    assert "stop(" in summary


def test_parse_error_summary_capped_at_200_chars():
    long_line = "Error in foo() : " + "x" * 300
    summary, _ = _parse_r_error(long_line)
    assert len(summary) <= 200


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
