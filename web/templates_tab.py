# web/templates_tab.py
"""模板配置标签页 —— 变量类型模板 + Config 模板（Section映射/pop/脚注/显示级别）。"""
from __future__ import annotations

import streamlit as st

from templates_io import (
    load_structure_templates, save_structure_templates, _BASE_TYPES,
    load_stat_groups_for_edit, save_statistical_formats,
)
from config_templates_io import load_config_templates, save_config_templates
from config_display_io import load_display_levels, save_display_levels, REQUIRED_FIELDS
from schema import CONFIG_COLS, StatItem, VALIDATION_RULES


# ── UI 辅助函数 ──────────────────────────────────────────────────────────────

def _edit_str_list(items: list, key_prefix: str, ver: int) -> list:
    """渲染可编辑字符串列表（单文本框 + 删除按钮），返回过滤空值后的新列表。"""
    result = []
    for j, val in enumerate(items):
        c1, c2 = st.columns([5, 0.5])
        with c1:
            new_val = st.text_input("值", value=val, label_visibility="collapsed",
                                    key=f"{key_prefix}_{ver}_{j}")
        with c2:
            if not st.button("🗑", key=f"{key_prefix}_del_{ver}_{j}"):
                if new_val.strip():
                    result.append(new_val.strip())
    return result


def _edit_children_list(children: list, key_prefix: str, ver: int) -> list:
    """渲染 Label+Aval 子行列表（双文本框 + 删除按钮），返回新列表。"""
    result = []
    for j, child in enumerate(children):
        c1, c2, c3 = st.columns([3, 3, 0.5])
        with c1:
            lbl = st.text_input("Label", value=child.get("Label", ""),
                                label_visibility="collapsed",
                                key=f"{key_prefix}_lbl_{ver}_{j}")
        with c2:
            avl = st.text_input("Aval", value=child.get("Aval", ""),
                                label_visibility="collapsed",
                                key=f"{key_prefix}_avl_{ver}_{j}")
        with c3:
            if not st.button("🗑", key=f"{key_prefix}_del_{ver}_{j}"):
                result.append({"Label": lbl, "Aval": avl})
    return result


# ── 主渲染函数 ────────────────────────────────────────────────────────────────

def render_stat_format_section(stat_ver: int) -> None:
    """渲染统计量格式模板编辑区。"""
    groups = load_stat_groups_for_edit()
    if not groups:
        st.info("未找到统计量格式模板，请检查 variable_templates.yaml")
        return

    tab_labels = [g.group_name for g in groups]
    tabs = st.tabs(tab_labels)

    for group, tab in zip(groups, tabs):
        with tab:
            if group.description:
                st.caption(group.description)

            for sg in group.subgroups:
                with st.expander(sg.subgroup_name, expanded=sg.default_expanded):
                    delete_indices: list[int] = []

                    for ii, item in enumerate(sg.items):
                        kb = f"sf_{group.group_id}_{sg.subgroup_id}_{ii}"

                        # 统计量名称 | 默认格式 | 默认勾选 | 删除
                        hc1, hc2, hc3, hc4 = st.columns([3.5, 2.5, 1, 0.5])
                        with hc1:
                            item.label = st.text_input(
                                "名称", value=item.label,
                                key=f"{kb}_lbl_{stat_ver}",
                                label_visibility="collapsed",
                                placeholder="统计量名称",
                            )
                        with hc2:
                            item.aval_template = st.text_input(
                                "默认格式", value=item.aval_template,
                                key=f"{kb}_tmpl_{stat_ver}",
                                label_visibility="collapsed",
                                placeholder="xx.x (xx.x, xx.x)",
                            )
                        with hc3:
                            item.default_checked = st.checkbox(
                                "默认勾选", value=item.default_checked,
                                key=f"{kb}_chk_{stat_ver}",
                            )
                        with hc4:
                            if st.button("🗑", key=f"{kb}_del_{stat_ver}", help="删除此统计量"):
                                delete_indices.append(ii)

                        # Aval 候选格式列表
                        oc1, oc2 = st.columns([6, 0.6])
                        with oc1:
                            st.caption("Aval 候选格式：")
                        with oc2:
                            if st.button("＋", key=f"{kb}_opt_add_{stat_ver}", help="添加候选格式"):
                                item.aval_options.append("")
                        item.aval_options = _edit_str_list(
                            item.aval_options, f"{kb}_opt", stat_ver
                        )

                        # 特殊值列表（NE / NR / <<0.001 等）
                        sv_list = list(item.special_values)
                        sc1, sc2 = st.columns([6, 0.6])
                        with sc1:
                            st.caption("特殊值（如 NE、NR、<<0.001）：")
                        with sc2:
                            if st.button("＋", key=f"{kb}_sv_add_{stat_ver}", help="添加特殊值"):
                                sv_list.append("")
                        item.special_values = _edit_str_list(
                            sv_list, f"{kb}_sv", stat_ver
                        )
                        st.divider()

                    # 应用删除
                    if delete_indices:
                        sg.items = [it for i, it in enumerate(sg.items) if i not in delete_indices]
                        st.cache_data.clear()
                        st.rerun()

                    # 新增统计量
                    if st.button(
                        "＋ 添加统计量",
                        key=f"sf_{group.group_id}_{sg.subgroup_id}_add_{stat_ver}",
                    ):
                        sg.items.append(StatItem(
                            item_id=f"custom_{len(sg.items)}",
                            label="",
                            aval_template="",
                        ))
                        st.cache_data.clear()
                        st.rerun()

    st.divider()
    if st.button("保存统计量格式模板", key="btn_save_stat_tmpl", type="secondary"):
        try:
            save_statistical_formats(groups, VALIDATION_RULES)
            st.cache_data.clear()
            st.session_state["stat_tmpl_version"] = stat_ver + 1
            st.success("统计量格式模板已保存")
        except OSError as e:
            st.error(f"保存失败：{e}")


def render_templates_tab() -> None:
    """渲染「模板配置」标签页全部内容。"""
    cfg_tmpl_ver = st.session_state.get("cfg_tmpl_version", 0)
    tmpl_ver = st.session_state.tmpl_version

    with st.expander("变量类型模板配置", expanded=True):
        templates_edit = load_structure_templates()

        st.caption("连续变量子行（Label + Aval 模板）")
        cont_children = templates_edit.get("连续变量", {}).get("children", [])
        new_children = _edit_children_list(cont_children, "tmpl", tmpl_ver)
        if st.button("＋ 添加子行", key="tmpl_add"):
            new_children.append({"Label": "", "Aval": ""})
        templates_edit.setdefault("连续变量", {})["children"] = new_children

        col_a, col_b = st.columns(2)
        with col_a:
            st.caption("分类变量-无子分类 Aval")
            templates_edit.setdefault("分类变量-无子分类", {})["aval"] = st.text_input(
                "Aval",
                value=templates_edit.get("分类变量-无子分类", {}).get("aval", "xx (xx.x)"),
                key="tmpl_cat_aval",
                label_visibility="collapsed",
            )
        with col_b:
            st.caption("日期变量 Aval")
            templates_edit.setdefault("日期变量", {})["aval"] = st.text_input(
                "Aval",
                value=templates_edit.get("日期变量", {}).get("aval", "YYYY-MM-DD"),
                key="tmpl_date_aval",
                label_visibility="collapsed",
            )

        st.caption("分类变量子分类 Aval 候选（子行 Aval 下拉选项）")
        aval_opts = list(templates_edit.get("分类变量-有子分类", {}).get("aval_options", ["xx (xx.x)"]))
        new_aval_opts = _edit_str_list(aval_opts, "tmpl_aval_opt", tmpl_ver)
        if st.button("＋ 添加候选 Aval", key="tmpl_aval_opt_add"):
            new_aval_opts.append("")
        templates_edit.setdefault("分类变量-有子分类", {})["aval_options"] = new_aval_opts

        custom_types = [k for k in templates_edit if k not in _BASE_TYPES]
        with st.expander(f"自定义变量类型（{len(custom_types)} 个）", expanded=bool(custom_types)):
            for ct in list(custom_types):
                ct_data = templates_edit[ct]
                st.markdown(f"**{ct}**")
                ct_col1, ct_col2 = st.columns([5, 1])
                with ct_col2:
                    if st.button("删除此类型", key=f"tmpl_del_type_{ct}"):
                        del templates_edit[ct]
                        st.rerun()
                with ct_col1:
                    st.caption("子行模板（Label + Aval）")
                ct_children = ct_data.get("children", [])
                new_ct_children = _edit_children_list(ct_children, f"tmpl_ct_{ct}", tmpl_ver)
                if st.button("＋ 添加子行", key=f"tmpl_ct_{ct}_add"):
                    new_ct_children.append({"Label": "", "Aval": ""})
                templates_edit[ct]["children"] = new_ct_children

                st.caption("子行 Aval 候选")
                ct_opts = list(ct_data.get("aval_options", []))
                new_ct_opts = _edit_str_list(ct_opts, f"tmpl_ct_{ct}_opt", tmpl_ver)
                if st.button("＋ 添加候选 Aval", key=f"tmpl_ct_{ct}_opt_add"):
                    new_ct_opts.append("")
                templates_edit[ct]["aval_options"] = new_ct_opts
                st.divider()

            new_type_key = f"tmpl_new_type_name_{tmpl_ver}"
            new_type_name = st.text_input("新变量类型名称", key=new_type_key, placeholder="如：生存分析指标")
            if st.button("＋ 新增变量类型", key="tmpl_add_type"):
                name = new_type_name.strip()
                if name and name not in templates_edit:
                    templates_edit[name] = {"children": [], "aval_options": []}
                    st.session_state.tmpl_version += 1
                    st.rerun()
                elif not name:
                    st.warning("请先输入类型名称")
                else:
                    st.warning(f"类型「{name}」已存在")

        if st.button("保存模板", key="btn_save_tmpl", type="secondary"):
            try:
                save_structure_templates(templates_edit)
                st.cache_data.clear()
                st.session_state.tmpl_version += 1
                st.success("模板已保存")
            except OSError as e:
                st.error(f"保存失败：{e}")

    with st.expander("⚙️ Config 模板配置", expanded=True):
        tab_trtlab, tab_sec, tab_pop, tab_fn, tab_levels = st.tabs(
            ["Trtlab 预设", "Section 映射", "pop 选项", "脚注片段", "显示级别"]
        )

        with tab_trtlab:
            cfg_tmpl_trt = load_config_templates()
            trt_presets: list = list(cfg_tmpl_trt.get("trtlab_presets", []))
            new_trt_presets: list = []
            for j, preset in enumerate(trt_presets):
                tc1, tc2, tc3 = st.columns([2.5, 3.5, 0.5])
                with tc1:
                    new_lbl = st.text_input(
                        "标签", value=preset.get("label", ""),
                        label_visibility="collapsed",
                        placeholder="如：14.1 三组",
                        key=f"cfgtmpl_trtlbl_{cfg_tmpl_ver}_{j}",
                    )
                with tc2:
                    new_val = st.text_input(
                        "值", value=preset.get("value", ""),
                        label_visibility="collapsed",
                        placeholder="如：试验组(N=xx)|对照组(N=xx)|合计(N=xx)",
                        key=f"cfgtmpl_trtval_{cfg_tmpl_ver}_{j}",
                    )
                with tc3:
                    if not st.button("🗑", key=f"cfgtmpl_trtdel_{cfg_tmpl_ver}_{j}"):
                        if new_lbl.strip():
                            new_trt_presets.append({"label": new_lbl.strip(), "value": new_val})
            if st.button("＋ 添加预设", key="cfgtmpl_trtadd"):
                new_trt_presets.append({"label": "", "value": ""})
            cfg_tmpl_trt["trtlab_presets"] = new_trt_presets
            if st.button("保存 Trtlab 预设", key="btn_save_trtlab", type="secondary"):
                try:
                    save_config_templates(cfg_tmpl_trt)
                    st.cache_data.clear()
                    st.session_state["cfg_tmpl_version"] = cfg_tmpl_ver + 1
                    st.success("已保存")
                except OSError as e:
                    st.error(f"保存失败：{e}")

        with tab_sec:
            cfg_tmpl_edit = load_config_templates()
            sec_map: dict = dict(cfg_tmpl_edit.get("section_map", {}))
            sec_items = list(sec_map.items())
            new_sec_map: dict = {}
            for j, (k, v) in enumerate(sec_items):
                sc1, sc2, sc3 = st.columns([2, 3, 0.5])
                with sc1:
                    new_k = st.text_input(
                        "Section no", value=k, label_visibility="collapsed",
                        key=f"cfgtmpl_secno_{cfg_tmpl_ver}_{j}",
                    )
                with sc2:
                    new_v = st.text_input(
                        "Section title", value=v, label_visibility="collapsed",
                        key=f"cfgtmpl_sectitle_{cfg_tmpl_ver}_{j}",
                    )
                with sc3:
                    if not st.button("🗑", key=f"cfgtmpl_secdel_{cfg_tmpl_ver}_{j}"):
                        if new_k.strip():
                            new_sec_map[new_k.strip()] = new_v
            if st.button("＋ 添加 Section", key="cfgtmpl_secadd"):
                new_sec_map[""] = ""
            cfg_tmpl_edit["section_map"] = new_sec_map
            if st.button("保存 Section 映射", key="btn_save_secmap", type="secondary"):
                try:
                    save_config_templates(cfg_tmpl_edit)
                    st.cache_data.clear()
                    st.session_state["cfg_tmpl_version"] = cfg_tmpl_ver + 1
                    st.success("已保存")
                except OSError as e:
                    st.error(f"保存失败：{e}")

        with tab_pop:
            cfg_tmpl_pop = load_config_templates()
            pop_opts: list = list(cfg_tmpl_pop.get("pop_options", []))
            new_pop_opts = _edit_str_list(pop_opts, "cfgtmpl_pop", cfg_tmpl_ver)
            if st.button("＋ 添加人群", key="cfgtmpl_popadd"):
                new_pop_opts.append("")
            cfg_tmpl_pop["pop_options"] = new_pop_opts
            if st.button("保存 pop 选项", key="btn_save_pop", type="secondary"):
                try:
                    save_config_templates(cfg_tmpl_pop)
                    st.cache_data.clear()
                    st.session_state["cfg_tmpl_version"] = cfg_tmpl_ver + 1
                    st.success("已保存")
                except OSError as e:
                    st.error(f"保存失败：{e}")

        with tab_fn:
            cfg_tmpl_fn = load_config_templates()
            fn_snippets: list = list(cfg_tmpl_fn.get("footnote_snippets", []))
            new_fn_snippets = _edit_str_list(fn_snippets, "cfgtmpl_fn", cfg_tmpl_ver)
            if st.button("＋ 添加片段", key="cfgtmpl_fnadd"):
                new_fn_snippets.append("")
            cfg_tmpl_fn["footnote_snippets"] = new_fn_snippets
            if st.button("保存脚注片段", key="btn_save_fn", type="secondary"):
                try:
                    save_config_templates(cfg_tmpl_fn)
                    st.cache_data.clear()
                    st.session_state["cfg_tmpl_version"] = cfg_tmpl_ver + 1
                    st.success("已保存")
                except OSError as e:
                    st.error(f"保存失败：{e}")

        with tab_levels:
            disp_cfg = load_display_levels()
            field_levels: dict = disp_cfg.get("field_levels", {})
            level_options = ["一级", "二级", "不显示"]
            level_map = {"level1": "一级", "level2": "二级", "hidden": "不显示"}
            level_rev = {"一级": "level1", "二级": "level2", "不显示": "hidden"}
            new_field_levels: dict = {}
            st.caption("字段  →  显示级别（必显示字段锁定不可修改）")
            for field in CONFIG_COLS:
                cur_level = field_levels.get(field, "level2")
                if field in REQUIRED_FIELDS:
                    st.text(f"  {field:<28} 必显示 🔒")
                    new_field_levels[field] = "required"
                else:
                    cur_label = level_map.get(cur_level, "二级")
                    lc1, lc2 = st.columns([3, 1.5])
                    with lc1:
                        st.caption(field)
                    with lc2:
                        new_label = st.selectbox(
                            field, options=level_options,
                            index=level_options.index(cur_label),
                            key=f"disp_level_{cfg_tmpl_ver}_{field}",
                            label_visibility="collapsed",
                        )
                    new_field_levels[field] = level_rev[new_label]
            if st.button("保存显示设置", key="btn_save_disp", type="secondary"):
                try:
                    save_display_levels({
                        "default_collapse": disp_cfg.get("default_collapse", True),
                        "field_levels": new_field_levels,
                    })
                    st.cache_data.clear()
                    st.session_state["cfg_tmpl_version"] = cfg_tmpl_ver + 1
                    st.success("显示设置已保存")
                except OSError as e:
                    st.error(f"保存失败：{e}")

    stat_ver = st.session_state.get("stat_tmpl_version", 0)
    with st.expander("📊 统计量格式模板配置", expanded=False):
        render_stat_format_section(stat_ver)
