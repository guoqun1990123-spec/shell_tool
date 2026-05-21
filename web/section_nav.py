# web/section_nav.py
"""左侧章节导航树 —— 纯视图层，不修改数据。"""
from __future__ import annotations
import re
import streamlit as st

_NAV_STATE_KEY = "section_nav_state"   # { sec_no: collapsed:bool }
_NAV_FILTER_KEY = "section_nav_filter" # { "section": str, "scroll_to": str|None }


def _nav_state() -> dict:
    if _NAV_STATE_KEY not in st.session_state:
        st.session_state[_NAV_STATE_KEY] = {}
    return st.session_state[_NAV_STATE_KEY]


def _nav_filter() -> dict:
    if _NAV_FILTER_KEY not in st.session_state:
        st.session_state[_NAV_FILTER_KEY] = {"section": "", "scroll_to": None}
    return st.session_state[_NAV_FILTER_KEY]


def _sec_sort_key(sec_no: str) -> tuple:
    """将 '14.1.2' 拆成 (14, 1, 2) 用于数值排序。"""
    parts = re.split(r"[.\-]", sec_no.strip())
    result = []
    for p in parts:
        try:
            result.append(int(p))
        except ValueError:
            result.append(p)
    return tuple(result)


def group_by_section(card_state: list[dict]) -> list[dict]:
    """
    将 card_state 按 Section no 分组，返回有序列表：
    [
      {
        "section_no": "14.1",
        "section_title": "人口学",
        "items": [card_dict, ...],
      },
      ...
    ]
    """
    groups: dict[str, dict] = {}
    for card in card_state:
        sec = str(card.get("Section no") or "").strip()
        if not sec:
            sec = "（无章节）"
        if sec not in groups:
            groups[sec] = {
                "section_no": sec,
                "section_title": str(card.get("Section title") or "").strip(),
                "items": [],
            }
        groups[sec]["items"].append(card)

    return sorted(groups.values(), key=lambda g: _sec_sort_key(g["section_no"]))
