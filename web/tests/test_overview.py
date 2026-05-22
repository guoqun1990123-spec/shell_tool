"""overview 纯函数单元测试。"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from overview import compute_section_stats


def test_empty_returns_totals_row_only():
    result = compute_section_stats([])
    assert result == [{"section_no": "合计", "section_title": "",
                       "表": 0, "图": 0, "列表": 0, "合计": 0}]


def test_basic_counts():
    cards = [
        {"Section no": "14.1", "Section title": "人口学", "cat": "表"},
        {"Section no": "14.1", "Section title": "人口学", "cat": "表"},
        {"Section no": "14.2", "Section title": "安全性", "cat": "图"},
    ]
    rows = compute_section_stats(cards)
    data = [r for r in rows if r["section_no"] != "合计"]
    assert data[0]["section_no"] == "14.1"
    assert data[0]["表"] == 2
    assert data[0]["合计"] == 2
    assert data[1]["section_no"] == "14.2"
    assert data[1]["图"] == 1
    assert data[1]["合计"] == 1


def test_totals_row():
    cards = [
        {"Section no": "14.1", "cat": "表"},
        {"Section no": "14.2", "cat": "列表"},
    ]
    rows = compute_section_stats(cards)
    totals = rows[-1]
    assert totals["section_no"] == "合计"
    assert totals["表"] == 1
    assert totals["列表"] == 1
    assert totals["合计"] == 2


def test_section_sorted_numerically():
    cards = [
        {"Section no": "14.10", "cat": "表"},
        {"Section no": "14.2", "cat": "表"},
        {"Section no": "14.1", "cat": "表"},
    ]
    rows = compute_section_stats(cards)
    data = [r["section_no"] for r in rows if r["section_no"] != "合计"]
    assert data == ["14.1", "14.2", "14.10"]


def test_no_section_sorts_last():
    cards = [
        {"Section no": "", "cat": "表"},
        {"Section no": "14.1", "cat": "表"},
    ]
    rows = compute_section_stats(cards)
    data = [r["section_no"] for r in rows if r["section_no"] != "合计"]
    assert data[0] == "14.1"
    assert data[-1] == "（无章节）"
