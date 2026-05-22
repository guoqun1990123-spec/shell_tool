# web/section_table.py
"""章节批量编辑表格视图。"""
from __future__ import annotations
import streamlit as st

from config_editor import (
    _CARD_STATE_KEY,
    _FOCUS_KEY,
    _update_card,
    _compute_table_nos,
    _delete_card,
    _render_level1,
    _empty_card,
    _insert_after,
    _add_card,
    CAT_OPTIONS,
)

_CHECKED_KEY = "table_checked_ids"      # set[str] — 当前勾选的 card_id
_EXPANDED_KEY = "table_expanded_rows"   # set[str] — 就地展开的 card_id
_VERSION_KEY = "table_editor_version"   # int — 强制 widget key 刷新


def _checked() -> set:
    if _CHECKED_KEY not in st.session_state:
        st.session_state[_CHECKED_KEY] = set()
    return st.session_state[_CHECKED_KEY]


def _expanded() -> set:
    if _EXPANDED_KEY not in st.session_state:
        st.session_state[_EXPANDED_KEY] = set()
    return st.session_state[_EXPANDED_KEY]


def _version() -> int:
    return st.session_state.get(_VERSION_KEY, 0)


def render_section_table(
    card_state: list[dict],
    sec_no: str,
    dataset_keys: list[str],
    cfg_templates: dict,
) -> None:
    """渲染章节批量编辑表格视图（主入口）。"""
    sec_cards = [c for c in card_state if str(c.get("Section no") or "").strip() == sec_no]

    _render_header(sec_no, sec_cards, dataset_keys, cfg_templates)
    _render_bulk_bar(sec_cards, dataset_keys, cfg_templates)
    _render_column_header()

    ver = _version()
    for card in sec_cards:
        _render_row(card, dataset_keys, cfg_templates, ver)


def _render_header(
    sec_no: str,
    sec_cards: list[dict],
    dataset_keys: list[str],
    cfg_templates: dict,
) -> None:
    """章节标题行 + [+ 添加TFL] 按钮。"""
    sec_title = ""
    if sec_cards:
        sec_title = str(sec_cards[0].get("Section title") or "").strip()

    col_title, col_add = st.columns([5, 1])
    with col_title:
        display = f"{sec_no} {sec_title}".strip() if sec_title else sec_no
        st.subheader(display)
    with col_add:
        if st.button("＋ 添加TFL", key=f"tbl_add_{sec_no}"):
            card_state = st.session_state[_CARD_STATE_KEY]
            if sec_cards:
                last_id = sec_cards[-1]["_id"]
                new_state = _insert_after(card_state, last_id)
                for c in new_state:
                    if c["_id"] not in {x["_id"] for x in card_state}:
                        new_state = _update_card(new_state, c["_id"],
                                                 **{"Section no": sec_no})
                        break
            else:
                new_state = _add_card(card_state)
                for c in new_state:
                    if c["_id"] not in {x["_id"] for x in card_state}:
                        new_state = _update_card(new_state, c["_id"],
                                                 **{"Section no": sec_no})
                        break
            st.session_state[_CARD_STATE_KEY] = new_state
            st.session_state[_VERSION_KEY] = _version() + 1
            st.rerun()


def _render_bulk_bar(
    sec_cards: list[dict],
    dataset_keys: list[str],
    cfg_templates: dict,
) -> None:
    """批量操作栏：全选 / 删除 / 修改pop / 修改Datasets。"""
    checked = _checked()
    sec_ids = {c["_id"] for c in sec_cards}
    all_checked = bool(sec_ids) and sec_ids <= checked

    pop_options: list[str] = cfg_templates.get("pop_options", [])

    col_all, col_del, col_pop, col_ds, col_spacer = st.columns([0.8, 1.2, 1.5, 1.5, 3])

    with col_all:
        new_all = st.checkbox("全选", value=all_checked, key=f"tbl_chk_all_{len(sec_cards)}")
        if new_all != all_checked:
            if new_all:
                checked |= sec_ids
            else:
                checked -= sec_ids
            st.session_state[_CHECKED_KEY] = checked
            st.rerun()

    with col_del:
        sel_in_sec = checked & sec_ids
        if st.button(f"删除选中({len(sel_in_sec)})", key="tbl_bulk_del",
                     disabled=not sel_in_sec):
            st.session_state["tbl_confirm_del"] = True

    if st.session_state.get("tbl_confirm_del"):
        sel_in_sec = checked & sec_ids
        st.warning(f"确认删除选中的 {len(sel_in_sec)} 条 TFL？")
        cy, cn = st.columns(2)
        with cy:
            if st.button("确认删除", key="tbl_del_yes", type="primary"):
                state = st.session_state[_CARD_STATE_KEY]
                for cid in list(sel_in_sec):
                    state = _delete_card(state, cid)
                st.session_state[_CARD_STATE_KEY] = state
                checked -= sel_in_sec
                st.session_state[_CHECKED_KEY] = checked
                st.session_state["tbl_confirm_del"] = False
                st.rerun()
        with cn:
            if st.button("取消", key="tbl_del_no"):
                st.session_state["tbl_confirm_del"] = False
                st.rerun()

    with col_pop:
        sel_in_sec = checked & sec_ids
        if sel_in_sec and pop_options:
            new_pop = st.selectbox("批量设pop", ["—"] + pop_options,
                                   key="tbl_bulk_pop", label_visibility="collapsed")
            if new_pop and new_pop != "—":
                state = st.session_state[_CARD_STATE_KEY]
                for cid in sel_in_sec:
                    state = _update_card(state, cid, pop=new_pop)
                st.session_state[_CARD_STATE_KEY] = state
                st.rerun()
        else:
            st.caption("修改pop▼")

    with col_ds:
        sel_in_sec = checked & sec_ids
        if sel_in_sec and dataset_keys:
            new_ds = st.selectbox("批量设Datasets", ["—"] + dataset_keys,
                                  key="tbl_bulk_ds", label_visibility="collapsed")
            if new_ds and new_ds != "—":
                state = st.session_state[_CARD_STATE_KEY]
                for cid in sel_in_sec:
                    state = _update_card(state, cid, Datasets=new_ds)
                st.session_state[_CARD_STATE_KEY] = state
                st.rerun()
        else:
            st.caption("修改Datasets▼")


def _render_column_header() -> None:
    """列标题行（纯文本标签）。"""
    st.divider()
    h0, h1, h2, h3, h4, h5, h6 = st.columns([0.5, 1.5, 0.8, 3.0, 1.5, 1.5, 0.5])
    with h0: st.caption("☑")
    with h1: st.caption("table no")
    with h2: st.caption("cat")
    with h3: st.caption("title")
    with h4: st.caption("pop")
    with h5: st.caption("Datasets")
    with h6: st.caption("⊞")
    st.divider()


def _render_row(
    card: dict,
    dataset_keys: list[str],
    cfg_templates: dict,
    ver: int,
) -> None:
    """渲染单行：checkbox + 5列即时编辑字段 + 展开按钮。"""
    card_id = card["_id"]
    checked = _checked()
    expanded = _expanded()
    pop_options: list[str] = cfg_templates.get("pop_options", [])

    is_checked = card_id in checked
    is_expanded = card_id in expanded

    c0, c1, c2, c3, c4, c5, c6 = st.columns([0.5, 1.5, 0.8, 3.0, 1.5, 1.5, 0.5])

    with c0:
        new_chk = st.checkbox("", value=is_checked, key=f"tbl_chk_{card_id}_{ver}",
                              label_visibility="collapsed")
        if new_chk != is_checked:
            if new_chk:
                checked.add(card_id)
            else:
                checked.discard(card_id)
            st.session_state[_CHECKED_KEY] = checked
            st.rerun()

    with c1:
        cur_tbl = str(card.get("table no") or "")
        tbl_overridden = bool(card.get("_tableno_overridden"))
        tbl_label = "⚠️手动" if tbl_overridden else "table no"
        new_tbl = st.text_input(tbl_label, value=cur_tbl,
                                key=f"tbl_tblno_{card_id}_{ver}",
                                label_visibility="collapsed")
        if new_tbl != cur_tbl:
            state = st.session_state[_CARD_STATE_KEY]
            st.session_state[_CARD_STATE_KEY] = _update_card(
                state, card_id,
                **{"table no": new_tbl, "_tableno_overridden": bool(new_tbl.strip())},
            )
            st.rerun()
        if tbl_overridden:
            if st.button("↩重置", key=f"tbl_reset_tbl_{card_id}_{ver}"):
                state = st.session_state[_CARD_STATE_KEY]
                new_state = _update_card(state, card_id, _tableno_overridden=False)
                st.session_state[_CARD_STATE_KEY] = _compute_table_nos(new_state)
                st.rerun()

    with c2:
        cur_cat = str(card.get("cat") or "")
        new_cat = st.selectbox("cat", options=CAT_OPTIONS,
                               index=CAT_OPTIONS.index(cur_cat) if cur_cat in CAT_OPTIONS else 0,
                               key=f"tbl_cat_{card_id}_{ver}",
                               label_visibility="collapsed")
        if new_cat != cur_cat:
            state = st.session_state[_CARD_STATE_KEY]
            st.session_state[_CARD_STATE_KEY] = _update_card(state, card_id, cat=new_cat)
            st.rerun()

    with c3:
        cur_title = str(card.get("title") or "")
        btn_label = (cur_title[:34] + "…") if len(cur_title) > 34 else (cur_title or "（点击进入编辑）")
        if st.button(btn_label, key=f"tbl_goto_{card_id}_{ver}", use_container_width=True):
            st.session_state["section_nav_view_mode"] = "card"
            st.session_state[_FOCUS_KEY] = card_id
            st.session_state[_CARD_STATE_KEY] = _update_card(
                st.session_state[_CARD_STATE_KEY], card_id, _level="level1"
            )
            st.rerun()

    with c4:
        cur_pop = str(card.get("pop") or "")
        pop_opts = [""] + pop_options
        new_pop = st.selectbox("pop", options=pop_opts,
                               index=pop_opts.index(cur_pop) if cur_pop in pop_opts else 0,
                               key=f"tbl_pop_{card_id}_{ver}",
                               label_visibility="collapsed")
        if new_pop != cur_pop:
            state = st.session_state[_CARD_STATE_KEY]
            st.session_state[_CARD_STATE_KEY] = _update_card(state, card_id, pop=new_pop)
            st.rerun()

    with c5:
        cur_ds = str(card.get("Datasets") or "")
        ds_opts = [""] + dataset_keys
        new_ds = st.selectbox("Datasets", options=ds_opts,
                              index=ds_opts.index(cur_ds) if cur_ds in ds_opts else 0,
                              key=f"tbl_ds_{card_id}_{ver}",
                              label_visibility="collapsed")
        if new_ds != cur_ds:
            state = st.session_state[_CARD_STATE_KEY]
            st.session_state[_CARD_STATE_KEY] = _update_card(state, card_id, Datasets=new_ds)
            st.rerun()

    with c6:
        expand_icon = "⊟" if is_expanded else "⊞"
        if st.button(expand_icon, key=f"tbl_expand_{card_id}_{ver}"):
            if is_expanded:
                expanded.discard(card_id)
            else:
                expanded.add(card_id)
            st.session_state[_EXPANDED_KEY] = expanded
            st.rerun()

    if is_expanded:
        with st.container():
            card_state_now = st.session_state[_CARD_STATE_KEY]
            cur_card = next((c for c in card_state_now if c["_id"] == card_id), card)
            _render_level1(cur_card, card_state_now, dataset_keys, cfg_templates, ver)

    st.divider()
