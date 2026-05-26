"""Config 主表卡片编辑器（三级显示系统）。"""
from __future__ import annotations

import uuid

import pandas as pd
import streamlit as st

from schema import CONFIG_COLS, VALID_MACVAR
import tfl_preview as _tfl_preview

# ── 常量 ─────────────────────────────────────────────────────────────────────

CAT_OPTIONS = ["", "表", "图", "列表"]
_CARD_STATE_KEY = "config_card_state"
_SELECTED_ID_KEY = "_cfg_selected_id"
_SYNC_VER_KEY = "_cfg_editor_sync_ver"
_FOCUS_KEY = "_cfg_focus_id"
_FILTER_KEY = "_cfg_filter"
_MENU_OPEN_KEY = "cfg_menu_open"    # set[card_id]，⋮ 菜单展开状态
_DS_OPEN_KEY = "cfg_ds_panel_open"  # set[card_id]，Datasets 面板展开状态


def _menu_open() -> set:
    if _MENU_OPEN_KEY not in st.session_state:
        st.session_state[_MENU_OPEN_KEY] = set()
    return st.session_state[_MENU_OPEN_KEY]


def _ds_open() -> set:
    if _DS_OPEN_KEY not in st.session_state:
        st.session_state[_DS_OPEN_KEY] = set()
    return st.session_state[_DS_OPEN_KEY]


def _card_idx_in_state(card_id: str) -> int | None:
    """返回卡片在当前 card_state 中的下标，找不到返回 None。"""
    state = st.session_state.get(_CARD_STATE_KEY, [])
    for i, c in enumerate(state):
        if c["_id"] == card_id:
            return i
    return None


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
    cat = str(card.get("cat", "") or "")
    tableno = str(card.get("table no", "") or "")
    title = str(card.get("title", "") or "")
    tbl_overridden = bool(card.get("_tableno_overridden"))
    menu = _menu_open()
    is_menu_open = card_id in menu

    # 摘要信息字符串（展开状态时显示在 c_info）
    info_parts = [f"**{seq}**"]
    if sec:
        info_parts.append(sec)
    if cat:
        info_parts.append(cat)
    tbl_display = (tableno + " ⚠️") if tbl_overridden else tableno
    if tbl_display:
        info_parts.append(tbl_display)
    info_str = " · ".join(info_parts)

    # 7 列布局：收起 | 专注 | ▲ | ▼ | + | ⋮ | 信息/标题
    c_collapse, c_focus, c_up, c_dn, c_ins, c_more, c_info = st.columns(
        [0.55, 0.45, 0.28, 0.28, 0.28, 0.28, 4.5]
    )

    # 收起按钮（仅展开时显示）
    with c_collapse:
        if not is_collapsed:
            if st.button("收起▲", key=f"cfg_collapse_{card_id}_{version}"):
                menu.discard(card_id)
                st.session_state[_MENU_OPEN_KEY] = menu
                st.session_state[_CARD_STATE_KEY] = _update_card(
                    card_state, card_id, _level="collapsed"
                )
                st.rerun()

    # 专注 / 退出专注
    with c_focus:
        if is_focus:
            if st.button("退出🔍", key=f"cfg_unfocus_{card_id}_{version}"):
                st.session_state[_FOCUS_KEY] = None
                st.session_state[_CARD_STATE_KEY] = _update_card(
                    card_state, card_id, _level="level1"
                )
                st.rerun()
        else:
            if st.button("🔍", key=f"cfg_focus_{card_id}_{version}"):
                st.session_state[_FOCUS_KEY] = card_id
                st.session_state[_SELECTED_ID_KEY] = card_id
                st.session_state[_CARD_STATE_KEY] = _update_card(
                    card_state, card_id, _level="focus"
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
            new_state = _insert_after(card_state, card_id)
            default_trtlab = st.session_state.get("default_trtlab", "").strip()
            if default_trtlab:
                for c in new_state:
                    if c["_id"] not in {x["_id"] for x in card_state}:
                        new_state = _update_card(new_state, c["_id"], Trtlab=default_trtlab)
                        break
            st.session_state[_CARD_STATE_KEY] = new_state
            st.rerun()

    # ⋮ 菜单开关
    with c_more:
        if st.button("⋮", key=f"cfg_more_{card_id}_{version}"):
            if is_menu_open:
                menu.discard(card_id)
            else:
                menu.add(card_id)
            st.session_state[_MENU_OPEN_KEY] = menu
            st.rerun()

    # 信息区 / 标题展开入口
    with c_info:
        if is_collapsed:
            btn_label = f"▶ {title[:45]}" if title else "▶ （点击展开）"
            if st.button(btn_label, key=f"cfg_sel_{card_id}_{version}",
                         use_container_width=True):
                st.session_state[_SELECTED_ID_KEY] = card_id
                st.session_state[_CARD_STATE_KEY] = _update_card(
                    card_state, card_id, _level="level1"
                )
                st.rerun()
        else:
            title_short = (title[:50] + "…") if len(title) > 50 else title
            st.caption(f"{info_str} · {title_short}")

    # ⋮ 菜单展开行（复制 / 删除）
    if is_menu_open:
        m1, m2, _ = st.columns([0.8, 0.9, 5.0])
        with m1:
            if st.button("复制", key=f"cfg_copy_{card_id}_{version}"):
                menu.discard(card_id)
                st.session_state[_MENU_OPEN_KEY] = menu
                st.session_state[_CARD_STATE_KEY] = _copy_card(card_state, card_id)
                st.rerun()
        with m2:
            if st.button("🗑 删除", key=f"cfg_del_{card_id}_{version}"):
                menu.discard(card_id)
                st.session_state[_MENU_OPEN_KEY] = menu
                if st.session_state.get(_SELECTED_ID_KEY) == card_id:
                    st.session_state[_SELECTED_ID_KEY] = None
                if st.session_state.get(_FOCUS_KEY) == card_id:
                    st.session_state[_FOCUS_KEY] = None
                st.session_state[_CARD_STATE_KEY] = _delete_card(card_state, card_id)
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
    cur_ds = str(card.get("Datasets", "") or "")

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

        # Datasets 迷你面板
        ds_open_set = _ds_open()
        is_ds_open = card_id in ds_open_set
        ds_btn_label = (
            f"📎 {cur_ds}  {'收起▲' if is_ds_open else '展开▼'}"
            if cur_ds else "📎 未关联 Datasets"
        )
        if st.button(ds_btn_label, key=f"cfg_ds_toggle_{card_id}_{version}"):
            if is_ds_open:
                ds_open_set.discard(card_id)
            else:
                ds_open_set.add(card_id)
            st.session_state[_DS_OPEN_KEY] = ds_open_set
            st.rerun()

        if is_ds_open:
            datasets = st.session_state.get("datasets", {})
            if cur_ds and cur_ds in datasets:
                ds_df = datasets[cur_ds]
                st.dataframe(ds_df.head(20), height=150, use_container_width=True)
                if st.button("🗂 编辑 Datasets", key=f"cfg_ds_edit_{card_id}_{version}"):
                    st.session_state[_SELECTED_ID_KEY] = card_id
                    st.session_state["selected_row"] = _card_idx_in_state(card_id)
                    st.session_state["active_tab"] = "datasets"
                    st.rerun()
            else:
                st.caption("未关联 Datasets 或数据表尚未创建")

        # ── 编辑 / 预览 双 tab ────────────────────────────────────────────────
        tab_edit, tab_preview = st.tabs(["✏️ 编辑", "👁️ 预览"])

        with tab_edit:
            with st.expander("展开更多 ▼"):
                fn_snippets: list = templates.get("footnote_snippets", [])
                for fn in ["footnote1", "footnote2", "footnote3", "footnote4",
                           "footnote5", "footnote6", "footnote7"]:
                    if fn_snippets:
                        fn_col, fn_ins_col = st.columns([5, 1])
                        val = str(card.get(fn, "") or "")
                        new_val = fn_col.text_input(fn, value=val, key=f"cfg_{fn}_{card_id}_{version}")
                        if new_val != val:
                            st.session_state[_CARD_STATE_KEY] = _update_card(
                                st.session_state[_CARD_STATE_KEY], card_id, **{fn: new_val}
                            )
                            st.rerun()
                        chosen = fn_ins_col.selectbox(
                            "插入", ["＋"] + fn_snippets,
                            key=f"cfg_{fn}_ins_{card_id}_{version}",
                            label_visibility="collapsed",
                        )
                        if chosen != "＋":
                            cur = str(card.get(fn, "") or "")
                            merged = (cur + "；" + chosen).lstrip("；")
                            st.session_state[_CARD_STATE_KEY] = _update_card(
                                st.session_state[_CARD_STATE_KEY], card_id, **{fn: merged}
                            )
                            st.rerun()
                    else:
                        _field(st, card, fn, card_id, version)
                _render_level2(card, card_state, version)

        with tab_preview:
            _render_card_preview(card, card_id, version)


# ── 预览 tab ─────────────────────────────────────────────────────────────────


def _render_card_preview(card: dict, card_id: str, version: int) -> None:
    datasets = st.session_state.get("datasets", {})
    card_state = st.session_state.get(_CARD_STATE_KEY, [])
    cur_card = next((c for c in card_state if c["_id"] == card_id), card)

    html = _tfl_preview.render_preview(cur_card, datasets)
    st.markdown(html, unsafe_allow_html=True)

    st.divider()

    col_btn, col_status = st.columns([1.5, 3])
    with col_btn:
        if st.button("🔄 用R真实渲染", key=f"cfg_real_render_{card_id}_{version}",
                     help="调用R生成单表Word文档，可下载"):
            from renderer import run_preview as _run_preview
            with st.spinner("R 渲染中..."):
                result = _run_preview(cur_card, datasets)
            st.session_state["preview_result"] = result
            st.session_state["preview_card_title"] = str(
                cur_card.get("title") or cur_card.get("table no") or "TFL"
            )
            st.rerun()

    with col_status:
        pr = st.session_state.get("preview_result")
        if pr and pr.get("status") == "success":
            pr_title = st.session_state.get("preview_card_title", "TFL")
            size_kb = len(pr["output_bytes"]) // 1024 if pr.get("output_bytes") else 0
            st.download_button(
                label=f"📥 下载 {pr_title}.docx",
                data=pr["output_bytes"],
                file_name=f"preview_{pr_title}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                key=f"cfg_dl_{card_id}_{version}",
            )
            st.caption(f"文件大小 {size_kb} KB")
        elif pr and pr.get("status") == "error":
            st.error(pr.get("error_summary") or "渲染失败")


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
    # 兼容旧数据：level2 视为 level1（level2 字段已移入 expander）
    if level == "level2":
        level = "level1"

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

    _render_level1(card, card_state, dataset_keys, templates, version)
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
    _NAV_SELECTED_KEY = "section_nav_selected_id"  # 持久记录当前选中条目
    nav_filt = st.session_state.get(_NAV_FILTER_KEY, {})

    # 若无选中 section，自动选中第一个，避免渲染全部卡片
    if not focus_id and not nav_filt.get("section"):
        first_sec = next(
            (str(c.get("Section no", "") or "") for c in card_state if c.get("Section no")),
            "",
        )
        if first_sec:
            st.session_state[_NAV_FILTER_KEY] = {**nav_filt, "section": first_sec}
            st.rerun()
    scroll_to_id = nav_filt.get("scroll_to")
    if scroll_to_id:
        card_state_now = st.session_state[_CARD_STATE_KEY]
        # 把目标卡片展开为 level1，同 section 其他卡片全部收起
        new_state = []
        for c in card_state_now:
            if c["_id"] == scroll_to_id:
                new_state.append({**c, "_level": "level1"})
            elif str(c.get("Section no") or "") == nav_filt.get("section", ""):
                new_state.append({**c, "_level": "collapsed"})
            else:
                new_state.append(c)
        st.session_state[_CARD_STATE_KEY] = new_state
        st.session_state[_NAV_SELECTED_KEY] = scroll_to_id
        nav_filt["scroll_to"] = None
        st.session_state[_NAV_FILTER_KEY] = nav_filt
        st.rerun()

    # 专注模式横幅
    if focus_id:
        col_info, col_back = st.columns([4, 1])
        with col_info:
            st.info("🔍 专注模式中 — 点击卡片上的「退出🔍」按钮退出")
        with col_back:
            if st.button("← 返回表格", key="cfg_back_to_table"):
                st.session_state["section_nav_view_mode"] = "table"
                st.session_state[_FOCUS_KEY] = None
                st.rerun()

    # 顶部添加按钮
    if st.button("＋ 添加行", key=f"cfg_add_{version}"):
        st.session_state[_CARD_STATE_KEY] = _add_card(card_state)
        st.rerun()

    # 章节导航树控制渲染范围
    nav_section = st.session_state.get("section_nav_filter", {}).get("section", "")
    nav_selected_id = st.session_state.get("section_nav_selected_id")

    total = len(card_state)
    for i, card in enumerate(card_state):
        if not focus_id and nav_section and str(card.get("Section no") or "") != nav_section:
            continue
        # 导航树选中具体条目时，只渲染该卡片
        if not focus_id and nav_selected_id and card.get("_id") != nav_selected_id:
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
