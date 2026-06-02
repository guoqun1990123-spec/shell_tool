# web/config_tab.py
"""Config 章节标签页 —— 筛选栏 + 导航树 + 卡片/表格编辑器。"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from keys import CFG_CARD_STATE as _CFG_CARD_KEY, NAV_SELECTED_ID
from config_editor import (
    render_config_editor, _update_card, card_state_to_df,
)
from config_templates_io import load_config_templates
from section_nav import render_section_nav
from section_table import render_section_table


def render_config_tab() -> pd.DataFrame:
    """渲染「Config章节」标签页，返回当前 edited_config DataFrame。"""
    _current_card_state = st.session_state.get(_CFG_CARD_KEY, [])

    # 筛选栏（作用于左侧导航树）
    _all_sections = sorted(
        {str(c.get("Section no", "") or "") for c in _current_card_state if c.get("Section no")},
        key=lambda s: [int(x) if x.isdigit() else x for x in s.replace("-", ".").split(".")],
    )
    _nav_filt = st.session_state.get("cfg_nav_filter", {"section": "", "cats": [], "keyword": ""})
    _fc1, _fc2, _fc3 = st.columns([1.5, 2.0, 2.5])
    with _fc1:
        _sec_opts = ["全部"] + _all_sections
        _cur_sec = _nav_filt.get("section", "")
        _sel_sec = st.selectbox(
            "Section", options=_sec_opts,
            index=_sec_opts.index(_cur_sec) if _cur_sec in _sec_opts else 0,
            key="cfg_nav_flt_sec", label_visibility="collapsed",
        )
        _new_sec = "" if _sel_sec == "全部" else _sel_sec
        if _new_sec != _cur_sec:
            _nav_filt["section"] = _new_sec
            st.session_state["cfg_nav_filter"] = _nav_filt
            st.rerun()
    with _fc2:
        _new_cats = st.multiselect(
            "cat", options=["表", "图", "列表"],
            default=_nav_filt.get("cats", []),
            key="cfg_nav_flt_cat", label_visibility="collapsed", placeholder="cat（全部）",
        )
        if _new_cats != _nav_filt.get("cats", []):
            _nav_filt["cats"] = _new_cats
            st.session_state["cfg_nav_filter"] = _nav_filt
            st.rerun()
    with _fc3:
        _new_kw = st.text_input(
            "关键词", value=_nav_filt.get("keyword", ""),
            placeholder="关键词（title / table no）",
            key="cfg_nav_flt_kw", label_visibility="collapsed",
        )
        if _new_kw != _nav_filt.get("keyword", ""):
            _nav_filt["keyword"] = _new_kw
            st.session_state["cfg_nav_filter"] = _nav_filt
            st.rerun()

    _nav_col, _edit_col = st.columns([1, 3], gap="small")

    with _nav_col:
        render_section_nav(_current_card_state, st.session_state.get("cfg_nav_filter", {}))

    with _edit_col:
        dataset_keys = list(st.session_state.datasets.keys())
        cfg_templates = load_config_templates()

        _view_mode = st.session_state.get("section_nav_view_mode", "table")
        _table_sec = st.session_state.get("section_nav_table_section", "")
        _nav_selected = st.session_state.get(NAV_SELECTED_ID)

        # 有选中条目时强制卡片视图
        if _nav_selected:
            _view_mode = "card"

        # 默认表格视图：若无选中 section，自动选第一个
        if _view_mode == "table" and not _table_sec:
            _card_state_now = st.session_state.get(_CFG_CARD_KEY, [])
            _first_sec = next(
                (str(c.get("Section no", "") or "") for c in _card_state_now if c.get("Section no")),
                "",
            )
            if _first_sec:
                st.session_state["section_nav_table_section"] = _first_sec
                st.session_state["section_nav_view_mode"] = "table"
                _table_sec = _first_sec

        if _view_mode == "table" and _table_sec:
            render_section_table(
                st.session_state.get(_CFG_CARD_KEY, []),
                _table_sec,
                dataset_keys,
                cfg_templates,
            )
            return card_state_to_df(st.session_state.get(_CFG_CARD_KEY, []))
        else:
            edited_config, selected_id = render_config_editor(
                st.session_state.config_df,
                dataset_keys,
                cfg_templates,
            )
            if selected_id is not None:
                st.session_state.selected_id = selected_id
            return edited_config
