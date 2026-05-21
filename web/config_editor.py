"""Config 主表卡片编辑器（三级显示系统）。"""
from __future__ import annotations

import uuid

import pandas as pd
import streamlit as st

from schema import CONFIG_COLS, VALID_MACVAR

# ── 常量 ─────────────────────────────────────────────────────────────────────

CAT_OPTIONS = ["", "表", "图", "列表"]
_CARD_STATE_KEY = "config_card_state"
_SELECTED_ID_KEY = "_cfg_selected_id"
_SYNC_VER_KEY = "_cfg_editor_sync_ver"
_FOCUS_KEY = "_cfg_focus_id"
_FILTER_KEY = "_cfg_filter"

# ── 纯函数 ───────────────────────────────────────────────────────────────────


def _empty_card() -> dict:
    card: dict = {col: "" for col in CONFIG_COLS}
    card["_id"] = str(uuid.uuid4())
    card["_level"] = "collapsed"
    card["_title_overridden"] = False
    card["_tableno_overridden"] = False
    return card


def df_to_card_state(df: pd.DataFrame) -> list[dict]:
    if df is None or df.empty:
        return []
    rows: list[dict] = []
    for _, row in df.iterrows():
        card: dict = {}
        for col in CONFIG_COLS:
            val = row.get(col, "")
            card[col] = "" if (val is None or (isinstance(val, float) and pd.isna(val))) else val
        card["_id"] = str(uuid.uuid4())
        card["_level"] = "collapsed"
        card["_title_overridden"] = bool(str(card.get("Section title", "")).strip())
        card["_tableno_overridden"] = False
        rows.append(card)
    return rows


def card_state_to_df(card_state: list[dict]) -> pd.DataFrame:
    if not card_state:
        return pd.DataFrame(columns=CONFIG_COLS)
    rows: list[dict] = []
    for i, card in enumerate(card_state, start=1):
        row = {k: v for k, v in card.items() if not k.startswith("_")}
        row["SeqNum"] = i
        rows.append(row)
    return pd.DataFrame(rows, columns=CONFIG_COLS)


def _compute_table_nos(card_state: list[dict]) -> list[dict]:
    section_counters: dict[str, int] = {}
    result: list[dict] = []
    for card in card_state:
        card = dict(card)
        if not card.get("_tableno_overridden"):
            sec = str(card.get("Section no", "") or "").strip()
            cat = str(card.get("cat", "") or "").strip()
            if sec:
                n = section_counters.get(sec, 0) + 1
                section_counters[sec] = n
                prefix = "16.2" if cat == "列表" else sec
                card["table no"] = f"{prefix}.{n}.1"
        result.append(card)
    return result


def _update_card(card_state: list[dict], card_id: str, **kwargs) -> list[dict]:
    result: list[dict] = []
    needs_recompute = False
    for card in card_state:
        if card["_id"] == card_id:
            card = dict(card)
            for k, v in kwargs.items():
                card[k] = v
            if "Section no" in kwargs or "cat" in kwargs:
                needs_recompute = True
        result.append(card)
    if needs_recompute:
        result = _compute_table_nos(result)
    return result


def _move_card(card_state: list[dict], idx: int, direction: int) -> list[dict]:
    n = len(card_state)
    new_idx = idx + direction
    if new_idx < 0 or new_idx >= n:
        return card_state
    lst = list(card_state)
    lst[idx], lst[new_idx] = lst[new_idx], lst[idx]
    return _compute_table_nos(lst)


def _delete_card(card_state: list[dict], card_id: str) -> list[dict]:
    return _compute_table_nos([c for c in card_state if c["_id"] != card_id])


def _copy_card(card_state: list[dict], card_id: str) -> list[dict]:
    result: list[dict] = []
    for card in card_state:
        result.append(card)
        if card["_id"] == card_id:
            new_card = dict(card)
            new_card["_id"] = str(uuid.uuid4())
            new_card["_level"] = "collapsed"
            new_card["_tableno_overridden"] = False
            result.append(new_card)
    return _compute_table_nos(result)


def _add_card(card_state: list[dict]) -> list[dict]:
    return _compute_table_nos(list(card_state) + [_empty_card()])


def _insert_after(card_state: list[dict], card_id: str) -> list[dict]:
    result: list[dict] = []
    for card in card_state:
        result.append(card)
        if card["_id"] == card_id:
            result.append(_empty_card())
    return _compute_table_nos(result)


def _card_visible(card: dict, filt: dict) -> bool:
    sec_filter = filt.get("section", "")
    cats_filter = filt.get("cats", [])
    kw = filt.get("keyword", "").strip().lower()

    if sec_filter and str(card.get("Section no", "") or "") != sec_filter:
        return False
    if cats_filter and str(card.get("cat", "") or "") not in cats_filter:
        return False
    if kw:
        haystack = (
            str(card.get("title", "") or "").lower()
            + str(card.get("table no", "") or "").lower()
        )
        if kw not in haystack:
            return False
    return True


# ── session_state 辅助 ────────────────────────────────────────────────────────


def _ensure_card_state(config_df: pd.DataFrame) -> None:
    ver = st.session_state.get("editor_version", 0)
    if (
        _CARD_STATE_KEY not in st.session_state
        or st.session_state.get(_SYNC_VER_KEY) != ver
    ):
        st.session_state[_CARD_STATE_KEY] = _compute_table_nos(df_to_card_state(config_df))
        st.session_state[_SYNC_VER_KEY] = ver


def _ensure_filter() -> None:
    if _FILTER_KEY not in st.session_state:
        st.session_state[_FILTER_KEY] = {"section": "", "cats": [], "keyword": ""}


# ── 字段渲染辅助 ──────────────────────────────────────────────────────────────


def _field(container, card: dict, field: str, card_id: str, version: int,
           label: str | None = None) -> None:
    val = str(card.get(field, "") or "")
    new_val = container.text_input(
        label or field, value=val,
        key=f"cfg_{field}_{card_id}_{version}",
    )
    if new_val != val:
        st.session_state[_CARD_STATE_KEY] = _update_card(
            st.session_state[_CARD_STATE_KEY], card_id, **{field: new_val}
        )
        st.rerun()


# ── 卡片头部操作栏 ────────────────────────────────────────────────────────────


def _render_header(
    card: dict,
    idx: int,
    total: int,
    card_state: list[dict],
    version: int,
) -> None:
    card_id = card["_id"]
    level = card.get("_level", "collapsed")
    is_collapsed = level == "collapsed"
    is_focus = level == "focus"

    seq = idx + 1
    sec = str(card.get("Section no", "") or "")
    sec_title = str(card.get("Section title", "") or "")
    cat = str(card.get("cat", "") or "")
    tableno = str(card.get("table no", "") or "")
    title = str(card.get("title", "") or "")
    tbl_overridden = bool(card.get("_tableno_overridden"))

    sec_display = f"{sec} {sec_title}".strip() if sec_title else sec

    # 操作按钮列 + 信息列
    btn_cols = st.columns([0.7, 0.7, 0.4, 0.4, 0.4, 0.5, 0.4, 0.4,
                            0.6, 0.9, 0.6, 1.4, 2.8])
    (c_expand, c_more, c_up, c_dn, c_ins, c_copy, c_del, c_focus,
     c_seq, c_sec, c_cat, c_tbl, c_title) = btn_cols

    # 展开/收起/退出专注
    with c_expand:
        if is_focus:
            if st.button("退出🔍", key=f"cfg_unfocus_{card_id}_{version}"):
                st.session_state[_FOCUS_KEY] = None
                st.session_state[_CARD_STATE_KEY] = _update_card(
                    card_state, card_id, _level="level2"
                )
                st.rerun()
        elif is_collapsed:
            if st.button("展开▼", key=f"cfg_expand_{card_id}_{version}"):
                st.session_state[_CARD_STATE_KEY] = _update_card(
                    card_state, card_id, _level="level1"
                )
                st.rerun()
        else:
            if st.button("收起▲", key=f"cfg_collapse_{card_id}_{version}"):
                st.session_state[_CARD_STATE_KEY] = _update_card(
                    card_state, card_id, _level="collapsed"
                )
                st.rerun()

    # 更多/收杂（level1 → level2，level2 → level1）
    with c_more:
        if level == "level1":
            if st.button("更多▼", key=f"cfg_more_{card_id}_{version}"):
                st.session_state[_CARD_STATE_KEY] = _update_card(
                    card_state, card_id, _level="level2"
                )
                st.rerun()
        elif level == "level2":
            if st.button("收杂▲", key=f"cfg_less_{card_id}_{version}"):
                st.session_state[_CARD_STATE_KEY] = _update_card(
                    card_state, card_id, _level="level1"
                )
                st.rerun()

    with c_up:
        if st.button("▲", key=f"cfg_up_{card_id}_{version}", disabled=(idx == 0)):
            st.session_state[_CARD_STATE_KEY] = _move_card(card_state, idx, -1)
            st.rerun()

    with c_dn:
        if st.button("▼", key=f"cfg_dn_{card_id}_{version}", disabled=(idx == total - 1)):
            st.session_state[_CARD_STATE_KEY] = _move_card(card_state, idx, +1)
            st.rerun()

    with c_ins:
        if st.button("+", key=f"cfg_ins_{card_id}_{version}"):
            st.session_state[_CARD_STATE_KEY] = _insert_after(card_state, card_id)
            st.rerun()

    with c_copy:
        if st.button("复制", key=f"cfg_copy_{card_id}_{version}"):
            st.session_state[_CARD_STATE_KEY] = _copy_card(card_state, card_id)
            st.rerun()

    with c_del:
        if st.button("🗑", key=f"cfg_del_{card_id}_{version}"):
            if st.session_state.get(_SELECTED_ID_KEY) == card_id:
                st.session_state[_SELECTED_ID_KEY] = None
            if st.session_state.get(_FOCUS_KEY) == card_id:
                st.session_state[_FOCUS_KEY] = None
            st.session_state[_CARD_STATE_KEY] = _delete_card(card_state, card_id)
            st.rerun()

    with c_focus:
        if st.button("🔍", key=f"cfg_focus_{card_id}_{version}"):
            st.session_state[_FOCUS_KEY] = card_id
            st.session_state[_SELECTED_ID_KEY] = card_id
            st.session_state[_CARD_STATE_KEY] = _update_card(
                card_state, card_id, _level="focus"
            )
            st.rerun()

    with c_seq:
        st.caption(f"**{seq}**")

    with c_sec:
        st.caption(sec_display or "—")

    with c_cat:
        st.caption(cat or "—")

    with c_tbl:
        tbl_display = (tableno + " ⚠️") if tbl_overridden else tableno
        st.caption(tbl_display or "—")

    with c_title:
        btn_label = (title[:34] + "…") if len(title) > 34 else (title or "（点击选中）")
        if st.button(btn_label, key=f"cfg_sel_{card_id}_{version}", use_container_width=True):
            st.session_state[_SELECTED_ID_KEY] = card_id
            if is_collapsed:
                st.session_state[_CARD_STATE_KEY] = _update_card(
                    card_state, card_id, _level="level1"
                )
            st.rerun()


# ── Level1 字段 ───────────────────────────────────────────────────────────────


def _render_level1(
    card: dict,
    card_state: list[dict],
    dataset_keys: list[str],
    templates: dict,
    version: int,
) -> None:
    card_id = card["_id"]
    section_map: dict = templates.get("section_map", {})
    pop_options: list = templates.get("pop_options", [])
    sec = str(card.get("Section no", "") or "")
    cat = str(card.get("cat", "") or "")
    tableno = str(card.get("table no", "") or "")
    tbl_overridden = bool(card.get("_tableno_overridden"))
    title_overridden = bool(card.get("_title_overridden"))
    sec_title_val = str(card.get("Section title", "") or "")

    with st.container():
        # 行A: Section no / Section title / cat / table no
        rA1, rA2, rA3, rA4 = st.columns([1.2, 2.5, 1.0, 1.5])

        with rA1:
            sec_opts = [""] + list(section_map.keys())
            new_sec = st.selectbox(
                "Section no", options=sec_opts,
                index=sec_opts.index(sec) if sec in sec_opts else 0,
                key=f"cfg_secno_{card_id}_{version}",
            )
            if new_sec != sec:
                updates: dict = {"Section no": new_sec}
                if not title_overridden and new_sec in section_map:
                    updates["Section title"] = section_map[new_sec]
                st.session_state[_CARD_STATE_KEY] = _update_card(card_state, card_id, **updates)
                st.rerun()

        with rA2:
            lbl_st = "Section title" + (" ✏️" if title_overridden else "")
            new_sec_title = st.text_input(
                lbl_st, value=sec_title_val,
                key=f"cfg_sectitle_{card_id}_{version}",
            )
            if new_sec_title != sec_title_val:
                st.session_state[_CARD_STATE_KEY] = _update_card(
                    card_state, card_id,
                    **{"Section title": new_sec_title,
                       "_title_overridden": bool(new_sec_title.strip())},
                )
                st.rerun()
            if title_overridden and sec in section_map:
                auto_title = section_map[sec]
                if sec_title_val != auto_title:
                    if st.button(f"↩ 重置为「{auto_title}」",
                                 key=f"cfg_reset_title_{card_id}_{version}"):
                        st.session_state[_CARD_STATE_KEY] = _update_card(
                            card_state, card_id,
                            **{"Section title": auto_title, "_title_overridden": False},
                        )
                        st.rerun()

        with rA3:
            new_cat = st.selectbox(
                "cat", options=CAT_OPTIONS,
                index=CAT_OPTIONS.index(cat) if cat in CAT_OPTIONS else 0,
                key=f"cfg_cat_{card_id}_{version}",
            )
            if new_cat != cat:
                st.session_state[_CARD_STATE_KEY] = _update_card(card_state, card_id, cat=new_cat)
                st.rerun()

        with rA4:
            tbl_lbl = "table no" + (" ⚠️手动" if tbl_overridden else "")
            new_tbl = st.text_input(
                tbl_lbl, value=tableno,
                key=f"cfg_tbl_{card_id}_{version}",
            )
            if new_tbl != tableno:
                st.session_state[_CARD_STATE_KEY] = _update_card(
                    card_state, card_id,
                    **{"table no": new_tbl, "_tableno_overridden": bool(new_tbl.strip())},
                )
                st.rerun()
            if tbl_overridden:
                if st.button("↩ 重置自动编号", key=f"cfg_reset_tbl_{card_id}_{version}"):
                    new_state = _update_card(card_state, card_id, _tableno_overridden=False)
                    st.session_state[_CARD_STATE_KEY] = _compute_table_nos(new_state)
                    st.rerun()

        # 行B: title（全宽）
        _field(st, card, "title", card_id, version)

        # 行C: pop / MacVar / Datasets
        rC1, rC2, rC3 = st.columns([2.5, 1.5, 1.5])

        with rC1:
            cur_pop = str(card.get("pop", "") or "")
            cur_pop_list = [p.strip() for p in cur_pop.split(",") if p.strip()]
            all_pop = list(dict.fromkeys(pop_options + cur_pop_list))
            new_pop_list = st.multiselect(
                "pop", options=all_pop,
                default=[p for p in cur_pop_list if p in all_pop],
                key=f"cfg_pop_{card_id}_{version}",
            )
            new_pop = ", ".join(new_pop_list)
            if new_pop != cur_pop:
                st.session_state[_CARD_STATE_KEY] = _update_card(
                    card_state, card_id, pop=new_pop
                )
                st.rerun()

        with rC2:
            cur_macvar = str(card.get("MacVar", "") or "")
            new_macvar = st.selectbox(
                "MacVar", options=VALID_MACVAR,
                index=VALID_MACVAR.index(cur_macvar) if cur_macvar in VALID_MACVAR else 0,
                key=f"cfg_macvar_{card_id}_{version}",
            )
            if new_macvar != cur_macvar:
                st.session_state[_CARD_STATE_KEY] = _update_card(
                    card_state, card_id, MacVar=new_macvar
                )
                st.rerun()

        with rC3:
            cur_ds = str(card.get("Datasets", "") or "")
            ds_opts = [""] + dataset_keys
            new_ds = st.selectbox(
                "Datasets", options=ds_opts,
                index=ds_opts.index(cur_ds) if cur_ds in ds_opts else 0,
                key=f"cfg_ds_{card_id}_{version}",
            )
            if new_ds != cur_ds:
                st.session_state[_CARD_STATE_KEY] = _update_card(
                    card_state, card_id, Datasets=new_ds
                )
                st.rerun()

        # 行D: Trtlab
        _field(st, card, "Trtlab", card_id, version)

        # 行E: footnote（折叠 expander，整体属于 level1）
        with st.expander("脚注 (footnote1-7)"):
            for fn in ["footnote1", "footnote2", "footnote3", "footnote4",
                       "footnote5", "footnote6", "footnote7"]:
                _field(st, card, fn, card_id, version)


# ── Level2 字段 ───────────────────────────────────────────────────────────────


def _render_level2(card: dict, card_state: list[dict], version: int) -> None:
    card_id = card["_id"]
    with st.container():
        rF1, rF2, rF3 = st.columns(3)
        _field(rF1, card, "Dutoffdate", card_id, version)
        _field(rF2, card, "Source_Data", card_id, version)
        _field(rF3, card, "PgmNotes", card_id, version)

        rG1, rG2, rG3, rG4, rG5, rG6 = st.columns(6)
        _field(rG1, card, "Subgrp", card_id, version)
        _field(rG2, card, "Adcols", card_id, version)
        _field(rG3, card, "Varlab", card_id, version)
        _field(rG4, card, "Labparm", card_id, version)
        _field(rG5, card, "ByseqL", card_id, version)
        _field(rG6, card, "RefTFL", card_id, version)


# ── 单卡片渲染 ────────────────────────────────────────────────────────────────


def _render_card(
    card: dict,
    idx: int,
    total: int,
    card_state: list[dict],
    dataset_keys: list[str],
    templates: dict,
    version: int,
    focus_id: str | None,
) -> None:
    card_id = card["_id"]
    level = card.get("_level", "collapsed")

    # 专注模式下其他卡片只显示占位
    if focus_id and focus_id != card_id:
        sec = str(card.get("Section no", "") or "—")
        title = str(card.get("title", "") or "")
        st.caption(f"··· {idx + 1}. {sec} {title[:30]}")
        return

    _render_header(card, idx, total, card_state, version)

    if level == "collapsed":
        st.divider()
        return

    # level1 内容
    _render_level1(card, card_state, dataset_keys, templates, version)

    # level2 或 focus 时追加二级字段
    if level in ("level2", "focus"):
        _render_level2(card, card_state, version)

    st.divider()


# ── 筛选栏 ────────────────────────────────────────────────────────────────────


def _render_filter_bar(card_state: list[dict], version: int) -> None:
    _ensure_filter()
    filt = st.session_state[_FILTER_KEY]

    all_sections = sorted({str(c.get("Section no", "") or "") for c in card_state if c.get("Section no")})
    fc1, fc2, fc3 = st.columns([1.5, 2.0, 2.5])

    with fc1:
        sec_opts = ["全部"] + all_sections
        cur_sec = filt.get("section", "")
        sel_sec = st.selectbox(
            "Section", options=sec_opts,
            index=sec_opts.index(cur_sec) if cur_sec in sec_opts else 0,
            key=f"cfg_flt_sec_{version}",
            label_visibility="collapsed",
        )
        new_sec = "" if sel_sec == "全部" else sel_sec
        if new_sec != cur_sec:
            filt["section"] = new_sec
            st.session_state[_FILTER_KEY] = filt
            st.rerun()

    with fc2:
        cur_cats = filt.get("cats", [])
        new_cats = st.multiselect(
            "cat", options=["表", "图", "列表"],
            default=cur_cats,
            key=f"cfg_flt_cat_{version}",
            label_visibility="collapsed",
            placeholder="cat（全部）",
        )
        if new_cats != cur_cats:
            filt["cats"] = new_cats
            st.session_state[_FILTER_KEY] = filt
            st.rerun()

    with fc3:
        cur_kw = filt.get("keyword", "")
        new_kw = st.text_input(
            "关键词", value=cur_kw,
            placeholder="关键词（title / table no）",
            key=f"cfg_flt_kw_{version}",
            label_visibility="collapsed",
        )
        if new_kw != cur_kw:
            filt["keyword"] = new_kw
            st.session_state[_FILTER_KEY] = filt
            st.rerun()


# ── 主入口 ───────────────────────────────────────────────────────────────────


def render_config_editor(
    config_df: pd.DataFrame,
    dataset_keys: list[str],
    templates: dict,
) -> tuple[pd.DataFrame, int | None]:
    """Render card-based config editor with 3-level display system.

    Returns (edited_df, selected_row_idx).
    """
    _ensure_card_state(config_df)
    card_state: list[dict] = st.session_state[_CARD_STATE_KEY]
    version: int = st.session_state.get("editor_version", 0)
    focus_id: str | None = st.session_state.get(_FOCUS_KEY)

    # 处理章节导航树的 scroll_to 定位请求
    _NAV_FILTER_KEY = "section_nav_filter"
    nav_filt = st.session_state.get(_NAV_FILTER_KEY, {})
    scroll_to_id = nav_filt.get("scroll_to")
    if scroll_to_id:
        card_state_now = st.session_state[_CARD_STATE_KEY]
        for c in card_state_now:
            if c["_id"] == scroll_to_id and c.get("_level") == "collapsed":
                st.session_state[_CARD_STATE_KEY] = _update_card(
                    card_state_now, scroll_to_id, _level="level1"
                )
                break
        nav_filt["scroll_to"] = None
        st.session_state[_NAV_FILTER_KEY] = nav_filt

    # 专注模式横幅
    if focus_id:
        st.info(f"🔍 专注模式中  —  点击卡片上的「退出🔍」按钮退出")

    # 筛选栏（专注模式下隐藏）
    if not focus_id:
        _render_filter_bar(card_state, version)

    filt = st.session_state.get(_FILTER_KEY, {})

    # 顶部添加按钮
    if st.button("＋ 添加行", key=f"cfg_add_{version}"):
        st.session_state[_CARD_STATE_KEY] = _add_card(card_state)
        st.rerun()

    total = len(card_state)
    for i, card in enumerate(card_state):
        if not focus_id and not _card_visible(card, filt):
            continue
        # 章节导航树筛选
        _NAV_FILTER_KEY = "section_nav_filter"
        nav_section = st.session_state.get(_NAV_FILTER_KEY, {}).get("section", "")
        if not focus_id and nav_section and str(card.get("Section no") or "") != nav_section:
            continue
        _render_card(card, i, total, card_state, dataset_keys, templates, version, focus_id)

    final_state: list[dict] = st.session_state[_CARD_STATE_KEY]
    df = card_state_to_df(final_state)

    selected_id = st.session_state.get(_SELECTED_ID_KEY)
    selected_idx: int | None = None
    if selected_id:
        for i, c in enumerate(final_state):
            if c["_id"] == selected_id:
                selected_idx = i
                break

    return df, selected_idx
