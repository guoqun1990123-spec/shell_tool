# web/section_nav.py
"""左侧章节导航树 —— 纯视图层，不修改数据。"""
from __future__ import annotations
import re
import streamlit as st

_NAV_STATE_KEY = "section_nav_state"   # { sec_no: collapsed:bool }
_NAV_FILTER_KEY = "section_nav_filter" # { "section": str, "scroll_to": str|None }
_VIEW_MODE_KEY = "section_nav_view_mode"      # "card" | "table"
_TABLE_SECTION_KEY = "section_nav_table_section"  # 当前表格视图的 section_no


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

    return sorted(
        groups.values(),
        key=lambda g: (1,) if g["section_no"] == "（无章节）" else (0, *_sec_sort_key(g["section_no"])),
    )


def render_section_nav(card_state: list[dict], nav_filt: dict | None = None) -> None:
    """
    渲染左侧章节导航树。
    nav_filt: {"section": str, "cats": list, "keyword": str} 来自筛选栏
    副作用：更新 session_state[_NAV_FILTER_KEY]，供右侧卡片列表读取。
    """
    if nav_filt is None:
        nav_filt = {}

    filt_section = nav_filt.get("section", "")
    filt_cats = nav_filt.get("cats", [])
    filt_kw = nav_filt.get("keyword", "").strip().lower()

    def _item_visible(card: dict) -> bool:
        if filt_cats and str(card.get("cat", "") or "") not in filt_cats:
            return False
        if filt_kw:
            haystack = (
                str(card.get("title", "") or "").lower()
                + str(card.get("table no", "") or "").lower()
            )
            if filt_kw not in haystack:
                return False
        return True

    groups = group_by_section(card_state)
    nav = _nav_state()
    filt = _nav_filter()
    cur_section = filt.get("section", "")

    # 筛选栏 section 下拉与导航树 cur_section 同步
    if filt_section and filt_section != cur_section:
        filt["section"] = filt_section
        cur_section = filt_section
        st.session_state[_NAV_FILTER_KEY] = filt
    elif not filt_section and cur_section:
        # 筛选栏清空 section 时，导航树也清空
        filt["section"] = ""
        cur_section = ""
        st.session_state[_NAV_FILTER_KEY] = filt

    # 统计筛选后可见条目总数
    visible_total = sum(1 for c in card_state if _item_visible(c))

    # "全部" 按钮：清除导航树 section 选中，右侧保持不变
    all_active = cur_section == "" and not filt_section
    if st.button(
        f"{'● ' if all_active else '  '}全部（{visible_total}）",
        key="nav_all",
        use_container_width=True,
    ):
        filt["section"] = ""
        filt["scroll_to"] = None
        st.session_state[_NAV_FILTER_KEY] = filt
        st.rerun()

    st.divider()

    for group in groups:
        sec_no = group["section_no"]
        # 筛选栏 section 过滤
        if filt_section and sec_no != filt_section:
            continue
        # 导航树 cur_section 过滤（点章节标题后只显示该 section）
        if cur_section and sec_no != cur_section:
            continue

        sec_title = group["section_title"]
        items = group["items"]
        # 只统计通过 cat/关键词 过滤的条目数
        visible_items = [c for c in items if _item_visible(c)]
        if not visible_items and (filt_cats or filt_kw):
            continue
        count = len(visible_items)
        is_collapsed = nav.get(sec_no, False)
        is_active_sec = cur_section == sec_no

        toggle_icon = "▼" if not is_collapsed else "▶"
        active_mark = "● " if is_active_sec else "  "
        sec_label = f"{toggle_icon}{active_mark}{sec_no}"
        if sec_title:
            sec_label += f" {sec_title[:10]}"
        sec_label += f" ({count})"

        col_sec, col_toggle = st.columns([5, 1])
        with col_sec:
            if st.button(sec_label, key=f"nav_sec_{sec_no}", use_container_width=True):
                filt["section"] = sec_no
                filt["scroll_to"] = None
                nav[sec_no] = False
                st.session_state[_NAV_FILTER_KEY] = filt
                st.session_state[_NAV_STATE_KEY] = nav
                st.session_state[_VIEW_MODE_KEY] = "table"
                st.session_state[_TABLE_SECTION_KEY] = sec_no
                st.session_state["section_nav_selected_id"] = None
                st.rerun()

        with col_toggle:
            if st.button("⊟" if not is_collapsed else "⊞", key=f"nav_toggle_{sec_no}"):
                nav[sec_no] = not is_collapsed
                st.session_state[_NAV_STATE_KEY] = nav
                st.rerun()

        # 子条目列表（仅展开时显示）
        if not is_collapsed:
            for ci, card in enumerate(items):
                if not _item_visible(card):
                    continue
                card_id = card.get("_id") or f"{sec_no}_{ci}"
                tbl_no = str(card.get("table no") or "")
                title = str(card.get("title") or "")
                label_text = tbl_no
                if title:
                    label_text += f" {title[:20]}"
                    if len(title) > 20:
                        label_text += "…"

                selected_id = st.session_state.get("section_nav_selected_id")
                item_label = f"{'● ' if selected_id == card_id else '  '}{label_text}"

                if st.button(item_label, key=f"nav_item_{card_id}", use_container_width=True):
                    filt["section"] = sec_no
                    filt["scroll_to"] = card_id
                    nav[sec_no] = False
                    st.session_state[_NAV_FILTER_KEY] = filt
                    st.session_state[_NAV_STATE_KEY] = nav
                    st.session_state[_VIEW_MODE_KEY] = "card"
                    st.session_state["_cfg_focus_id"] = None
                    st.rerun()
