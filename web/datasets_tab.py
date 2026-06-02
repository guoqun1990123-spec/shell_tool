# web/datasets_tab.py
"""Datasets 标签页 —— 数据集创建、编辑、重命名、预览。"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from schema import (
    DATASET_TABLE_COLS, DATASET_LIST_COLS, DATASET_LIST_NUM_COLS,
)
from keys import (
    CFG_CARD_STATE as _CFG_CARD_KEY,
    CFG_FOCUS_ID, ACTIVE_TAB as _ACTIVE_TAB_KEY, TAB_SWITCH_REQ,
    MAIN_SELECTED_ID,
)
from dataset_editor import (
    state_key, df_to_card_state, render_dataset_editor,
    normalize_dataset_state, apply_normalize,
)
from templates_io import load_templates
from dataset_preview import render_preview, render_list_preview
from config_editor import _update_card


# ── 纯函数 ───────────────────────────────────────────────────────────────────

def _apply_rename_dataset(
    datasets: dict,
    card_state: list,
    ss_snapshot: dict,
    old_name: str,
    new_name: str,
) -> tuple:
    """计算数据集重命名后的完整新状态，不修改任何入参。

    返回 (new_datasets, new_card_state, add_keys, del_keys)：
    - new_datasets: 重命名后的 datasets dict
    - new_card_state: 所有 Datasets 字段同步更新后的 config 卡片列表
    - add_keys: {key: value}，需要写入 session_state 的新 key
    - del_keys: [key]，需要从 session_state 删除的旧 key
    """
    new_datasets = {(new_name if k == old_name else k): v for k, v in datasets.items()}

    new_card_state = [
        {**c, "Datasets": new_name}
        if str(c.get("Datasets") or "").strip() == old_name
        else c
        for c in card_state
    ]

    add_keys: dict = {}
    del_keys: list = []
    for old_key, new_key in [
        (state_key(old_name), state_key(new_name)),
        (f"_ds_version_{old_name}", f"_ds_version_{new_name}"),
    ]:
        if old_key in ss_snapshot:
            add_keys[new_key] = ss_snapshot[old_key]
            del_keys.append(old_key)

    return new_datasets, new_card_state, add_keys, del_keys


def _empty_dataset_table() -> pd.DataFrame:
    return pd.DataFrame(columns=DATASET_TABLE_COLS)


def _empty_dataset_list() -> pd.DataFrame:
    return pd.DataFrame(columns=DATASET_LIST_COLS)


def _invalidate_preview_cache(ds_name: str) -> None:
    """清除所有引用该数据集的 Config 卡片的静态预览缓存。"""
    for c in st.session_state.get(_CFG_CARD_KEY, []):
        if str(c.get("Datasets") or "").strip() == ds_name:
            cid = c["_id"]
            for k in (f"_preview_html_{cid}", f"_preview_sig_{cid}"):
                if k in st.session_state:
                    del st.session_state[k]


def _build_list_column_config() -> dict:
    cc = {}
    for col in DATASET_LIST_COLS:
        if col in DATASET_LIST_NUM_COLS:
            cc[col] = st.column_config.NumberColumn(col, step=1, min_value=0)
        else:
            cc[col] = st.column_config.TextColumn(col)
    return cc


# ── 主渲染函数 ────────────────────────────────────────────────────────────────

def render_datasets_tab() -> None:
    """渲染「Datasets」标签页全部内容。"""
    sel_id_ds = st.session_state.get(MAIN_SELECTED_ID)
    card_state_all = st.session_state.get(_CFG_CARD_KEY, [])
    sel_card = next((c for c in card_state_all if c.get("_id") == sel_id_ds), None) if sel_id_ds else None

    if sel_card is not None:
        ds_name = str(sel_card.get("Datasets", "") or "").strip()
        macvar = str(sel_card.get("MacVar", "") or "").strip()
        seq_no = sel_card.get("SeqNum", "?")
        tbl_no = str(sel_card.get("table no", "") or "").strip()
        title = str(sel_card.get("title", "") or "").strip()
        title_short = (title[:30] + "…") if len(title) > 30 else title

        _info_col, _back_col = st.columns([5, 1])
        with _info_col:
            st.caption(
                f"**{tbl_no}** {title_short}  ·  "
                f"SeqNum={seq_no}  ·  Datasets=`{ds_name}`  ·  MacVar=`{macvar}`"
            )
        with _back_col:
            if st.button("← Config", key="btn_back_to_config",
                         help="返回 Config 章节并定位到该卡片"):
                sel_id = st.session_state.get(MAIN_SELECTED_ID)
                if sel_id:
                    cs_back = st.session_state.get(_CFG_CARD_KEY, [])
                    st.session_state[_CFG_CARD_KEY] = _update_card(cs_back, sel_id, _level="focus")
                    st.session_state[CFG_FOCUS_ID] = sel_id
                    st.session_state["section_nav_view_mode"] = "card"
                st.session_state[_ACTIVE_TAB_KEY] = "config"
                st.session_state[TAB_SWITCH_REQ] = st.session_state.get(TAB_SWITCH_REQ, 0) + 1
                st.rerun()
    else:
        ds_name = ""
        st.info("请先在「Config章节」标签页中点击某行以选中，再切换此标签查看数据表。")

    # 新建数据表
    col_dsname, col_dscopy, col_dsadd = st.columns([2, 2, 1])
    with col_dsname:
        new_ds_name = st.text_input("新建数据表名", placeholder="如 t_demo", key="new_ds_name")
    with col_dscopy:
        existing_keys = list(st.session_state.datasets.keys())
        copy_from = st.selectbox(
            "复制自（可选）", ["— 空白 —"] + existing_keys,
            key="new_ds_copy_from",
        )
    with col_dsadd:
        st.write("")
        st.write("")
        if st.button("新建数据表", key="btn_add_ds"):
            if new_ds_name and new_ds_name not in st.session_state.datasets:
                if copy_from != "— 空白 —" and copy_from in st.session_state.datasets:
                    st.session_state.datasets[new_ds_name] = st.session_state.datasets[copy_from].copy()
                else:
                    is_list = new_ds_name == "list"
                    st.session_state.datasets[new_ds_name] = (
                        _empty_dataset_list() if is_list else _empty_dataset_table()
                    )
                # 若当前选中的 Config 行 Datasets 字段为空，自动关联
                cur_sel_id = st.session_state.get(MAIN_SELECTED_ID)
                if cur_sel_id:
                    cs = st.session_state.get(_CFG_CARD_KEY, [])
                    cur_card = next((c for c in cs if c["_id"] == cur_sel_id), None)
                    if cur_card and not str(cur_card.get("Datasets") or "").strip():
                        st.session_state[_CFG_CARD_KEY] = _update_card(cs, cur_sel_id, Datasets=new_ds_name)
                        st.toast("✅ 已自动关联到当前 TFL 的 Datasets 字段")
                st.rerun()

    # 共用数据集提示
    if ds_name:
        shared_cards = [
            c for c in card_state_all
            if str(c.get("Datasets") or "").strip() == ds_name
        ]
        if len(shared_cards) > 1:
            shared_labels = [str(c.get("table no") or c.get("SeqNum") or "?") for c in shared_cards]
            st.warning(
                f"⚠️ 此数据集被 **{len(shared_cards)}** 张表共用："
                f" {', '.join(shared_labels[:5])}"
                + ("…" if len(shared_labels) > 5 else "")
                + "。修改将影响所有引用此数据集的 TFL。"
            )

    # 数据集重命名
    if ds_name and ds_name in st.session_state.datasets:
        with st.expander("✏️ 重命名此数据集", expanded=False):
            _rename_col1, _rename_col2 = st.columns([3, 1])
            with _rename_col1:
                new_name_input = st.text_input(
                    "新名称", value=ds_name,
                    key=f"rename_ds_{ds_name}",
                    label_visibility="collapsed",
                )
            with _rename_col2:
                if st.button("确认重命名", key=f"btn_rename_ds_{ds_name}",
                             disabled=not new_name_input.strip() or new_name_input == ds_name):
                    new_name = new_name_input.strip()
                    if new_name in st.session_state.datasets:
                        st.error(f"数据集名 `{new_name}` 已存在，请换一个名称。")
                        st.stop()
                    else:
                        new_ds, new_cs, add, del_ = _apply_rename_dataset(
                            datasets=st.session_state.datasets,
                            card_state=st.session_state.get(_CFG_CARD_KEY, []),
                            ss_snapshot=dict(st.session_state),
                            old_name=ds_name,
                            new_name=new_name,
                        )
                        st.session_state.datasets = new_ds
                        st.session_state[_CFG_CARD_KEY] = new_cs
                        for k, v in add.items():
                            st.session_state[k] = v
                        for k in del_:
                            del st.session_state[k]
                        st.toast(f"✅ 已将数据集 `{ds_name}` 重命名为 `{new_name}`，并同步更新了所有引用")
                        st.rerun()

    if ds_name and ds_name in st.session_state.datasets:
        is_list = ds_name == "list"
        ds_df = st.session_state.datasets[ds_name]

        if is_list:
            tab_edit, tab_preview = st.tabs(["✏️ 编辑", "👁️ Listing 预览"])
            with tab_edit:
                ds_cc = _build_list_column_config()
                edited_ds = st.data_editor(
                    ds_df,
                    column_config=ds_cc,
                    num_rows="dynamic",
                    width="stretch",
                    key=f"ds_editor_{ds_name}_{st.session_state.editor_version}",
                )
                st.session_state.datasets[ds_name] = edited_ds
                _invalidate_preview_cache(ds_name)
            with tab_preview:
                render_list_preview(st.session_state.datasets[ds_name])
        else:
            card_key = state_key(ds_name)
            version_key = f"_ds_version_{ds_name}"
            templates = load_templates()
            if st.session_state.get(version_key) != st.session_state.editor_version:
                init_state = df_to_card_state(ds_df)
                _, conflicts = normalize_dataset_state(init_state, templates)
                if conflicts:
                    state_map = {r["_id"]: r for r in init_state}
                    auto_sel = {
                        c["child_id"] or c["parent_id"]
                        for c in conflicts
                        if not str(state_map.get(c["child_id"] or c["parent_id"], {}).get("Aval") or "").strip()
                    }
                    if auto_sel:
                        init_state = apply_normalize(init_state, conflicts, auto_sel)
                st.session_state[card_key] = init_state
                st.session_state[version_key] = st.session_state.editor_version

            tab_edit, tab_preview = st.tabs(["✏️ 编辑", "👁️ 结构预览"])
            with tab_edit:
                result_df = render_dataset_editor(ds_name, ds_df, templates)
                st.session_state.datasets[ds_name] = result_df
                _invalidate_preview_cache(ds_name)
            with tab_preview:
                render_preview(ds_name, st.session_state.get(card_key, []))

    elif ds_name:
        st.info(f"数据表 '{ds_name}' 尚未创建，请在上方新建。")
