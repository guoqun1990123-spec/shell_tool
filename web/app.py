"""TFL Shell 配置编辑器 —— Streamlit 入口"""
import tomllib
from pathlib import Path

import pandas as pd
import streamlit as st

from excel_io import list_excel_pairs, load_excel
from git_ops import GitOps, make_commit_msg, make_filename
from schema import (
    CONFIG_COLS,
    DATASET_LIST_COLS, DATASET_LIST_NUM_COLS,
    DATASET_TABLE_COLS, DATASET_TABLE_NUM_COLS,
)
from validators import validate
from dataset_editor import render_dataset_editor, df_to_card_state, state_key
from dataset_preview import render_preview
from templates_io import load_templates
from config_editor import render_config_editor, _CARD_STATE_KEY as _CFG_CARD_KEY, _FOCUS_KEY, _update_card
from config_templates_io import load_config_templates, save_config_templates
from renderer import run_render
from config_display_io import load_display_levels, save_display_levels, REQUIRED_FIELDS
from yaml_io import dump_yaml, list_yaml_files, load_yaml
from section_nav import render_section_nav
from section_table import render_section_table

# ── 配置加载 ────────────────────────────────────────────────────────────────

CONFIG_TOML = Path(__file__).parent / "config.toml"


@st.cache_resource
def _load_git_ops():
    if not CONFIG_TOML.exists():
        return None
    with open(CONFIG_TOML, "rb") as f:
        cfg = tomllib.load(f)
    g = cfg.get("git", {})
    try:
        return GitOps(
            repo_path=g.get("repo_path", str(Path(__file__).parent.parent)),
            remote=g.get("remote", "origin"),
            branch=g.get("branch", "main"),
            author_name=g.get("author_name", "TFL Web"),
            author_email=g.get("author_email", "tfl@local"),
        )
    except Exception:
        return None


def _repo_config_dir() -> Path:
    if not CONFIG_TOML.exists():
        return Path(__file__).parent.parent / "config"
    with open(CONFIG_TOML, "rb") as f:
        cfg = tomllib.load(f)
    return Path(cfg.get("git", {}).get("repo_path", str(Path(__file__).parent.parent))) / "config"


# ── Session state 初始化 ────────────────────────────────────────────────────

def _empty_config() -> pd.DataFrame:
    return pd.DataFrame(columns=CONFIG_COLS)


def _empty_dataset_table() -> pd.DataFrame:
    return pd.DataFrame(columns=DATASET_TABLE_COLS)


def _empty_dataset_list() -> pd.DataFrame:
    return pd.DataFrame(columns=DATASET_LIST_COLS)


def _init_state():
    if "config_df" not in st.session_state:
        st.session_state.config_df = _empty_config()
    if "datasets" not in st.session_state:
        st.session_state.datasets = {}
    if "selected_row" not in st.session_state:
        st.session_state.selected_row = None
    if "protocol_name" not in st.session_state:
        st.session_state.protocol_name = ""
    if "editor_version" not in st.session_state:
        st.session_state.editor_version = 0
    if "tmpl_version" not in st.session_state:
        st.session_state.tmpl_version = 0
    if "render_status" not in st.session_state:
        st.session_state.render_status = {
            "status": "idle",      # idle / pending / success / error
            "output_bytes": None,
            "output_name": None,
            "error_log": None,
            "error_summary": None,
            "seq_hint": None,
            "elapsed": None,
        }


def _build_list_column_config() -> dict:
    cc = {}
    for col in DATASET_LIST_COLS:
        if col in DATASET_LIST_NUM_COLS:
            cc[col] = st.column_config.NumberColumn(col, step=1, min_value=0)
        else:
            cc[col] = st.column_config.TextColumn(col)
    return cc


# ── 加载辅助 ────────────────────────────────────────────────────────────────

def _guess_dataset_pair(cfg_name: str, ds_names: list[str]) -> str:
    """config_ISS.xlsx → datasets_ISS.xlsx（找不到则返回首个）。"""
    stem = cfg_name.removeprefix("config_").removesuffix(".xlsx")
    target = f"datasets_{stem}.xlsx"
    return target if target in ds_names else (ds_names[0] if ds_names else "")


def _do_load(loader, success_msg: str):
    """统一加载入口：调用 loader()，成功则写入 session_state 并重置编辑器。"""
    try:
        cfg_df, dsets = loader()
        st.session_state.config_df = cfg_df
        st.session_state.datasets = dsets
        st.session_state.selected_row = None
        st.session_state.editor_version += 1
        st.success(success_msg)
    except Exception as e:
        st.error(f"加载失败：{e}")


# ── 主界面 ──────────────────────────────────────────────────────────────────

def main():
    st.set_page_config(page_title="TFL Shell 配置编辑器", layout="wide")
    _init_state()

    git_ops = _load_git_ops()
    config_dir = _repo_config_dir()

    # ── 顶部工具栏 ──────────────────────────────────────────────────────────
    col_proto, col_load, col_new = st.columns([2, 4, 1])

    with col_proto:
        st.session_state.protocol_name = st.text_input(
            "方案简称", value=st.session_state.protocol_name,
            placeholder="如 ISS、CSR_A"
        )

    with col_load:
        load_fmt = st.radio("加载格式", ["YAML", "Excel"], horizontal=True, key="load_fmt")
        if load_fmt == "YAML":
            yaml_files = list_yaml_files(config_dir)
            file_labels = ["-- 新建空白 --"] + [f.name for f in yaml_files]
            selected_file = st.selectbox("加载已有 YAML", file_labels, key="load_yaml_sel")
            if st.button("加载", key="btn_load_yaml") and selected_file != "-- 新建空白 --":
                _do_load(lambda p=config_dir / selected_file: load_yaml(p),
                         f"已加载 YAML：{selected_file}")
        else:
            cfg_files, ds_files = list_excel_pairs(config_dir)
            if not cfg_files or not ds_files:
                st.info("config 目录下未找到 config_*.xlsx / datasets_*.xlsx")
            else:
                cfg_names = [f.name for f in cfg_files]
                ds_names = [f.name for f in ds_files]
                cfg_sel = st.selectbox("config 文件", cfg_names, key="load_excel_cfg")
                default_ds = _guess_dataset_pair(cfg_sel, ds_names)
                ds_idx = ds_names.index(default_ds) if default_ds in ds_names else 0
                ds_sel = st.selectbox("datasets 文件", ds_names, index=ds_idx,
                                      key="load_excel_ds")
                if st.button("加载", key="btn_load_excel"):
                    _do_load(
                        lambda cp=config_dir / cfg_sel, dp=config_dir / ds_sel: load_excel(cp, dp),
                        f"已加载 Excel：{cfg_sel} + {ds_sel}",
                    )

    with col_new:
        if st.button("新建空白", key="btn_new"):
            st.session_state.config_df = _empty_config()
            st.session_state.datasets = {}
            st.session_state.selected_row = None
            st.session_state.editor_version += 1

    # ── Config 主表（左右分栏）──────────────────────────────────────────────
    st.subheader("Config 主表")

    _nav_col, _edit_col = st.columns([1, 3], gap="small")

    with _nav_col:
        _current_card_state = st.session_state.get(_CFG_CARD_KEY, [])
        render_section_nav(_current_card_state)

    with _edit_col:
        dataset_keys = list(st.session_state.datasets.keys())
        cfg_templates = load_config_templates()

        _view_mode = st.session_state.get("section_nav_view_mode", "card")
        _table_sec = st.session_state.get("section_nav_table_section", "")

        if _view_mode == "table" and _table_sec:
            render_section_table(
                st.session_state.get(_CFG_CARD_KEY, []),
                _table_sec,
                dataset_keys,
                cfg_templates,
            )
            from config_editor import card_state_to_df
            edited_config = card_state_to_df(st.session_state.get(_CFG_CARD_KEY, []))
            selected_idx = st.session_state.selected_row
        else:
            edited_config, selected_idx = render_config_editor(
                st.session_state.config_df,
                dataset_keys,
                cfg_templates,
            )
            st.session_state.selected_row = selected_idx

    # ── 校验 ─────────────────────────────────────────────────────────────────
    errors = validate(edited_config, st.session_state.datasets)

    # ── Datasets 子表 ───────────────────────────────────────────────────────
    st.divider()
    st.subheader("Datasets 子表")

    sel_idx = selected_idx
    if sel_idx is not None and sel_idx < len(edited_config):
        sel_row = edited_config.iloc[sel_idx]
        ds_name = str(sel_row.get("Datasets", "") or "").strip()
        macvar = str(sel_row.get("MacVar", "") or "").strip()
        seq_no = sel_row.get("SeqNum", "?")
        st.caption(f"当前选中：SeqNum={seq_no}，Datasets='{ds_name}'，MacVar='{macvar}'")

        col_dsname, col_dsadd = st.columns([3, 1])
        with col_dsname:
            new_ds_name = st.text_input("新建数据表名", placeholder="如 t_demo", key="new_ds_name")
        with col_dsadd:
            st.write("")
            if st.button("新建数据表", key="btn_add_ds"):
                if new_ds_name and new_ds_name not in st.session_state.datasets:
                    is_list = new_ds_name == "list"
                    st.session_state.datasets[new_ds_name] = (
                        _empty_dataset_list() if is_list else _empty_dataset_table()
                    )
                    st.rerun()

        if ds_name and ds_name in st.session_state.datasets:
            is_list = ds_name == "list"
            ds_df = st.session_state.datasets[ds_name]

            if is_list:
                # list 子表保持原 data_editor
                ds_cc = _build_list_column_config()
                edited_ds = st.data_editor(
                    ds_df,
                    column_config=ds_cc,
                    num_rows="dynamic",
                    width="stretch",
                    key=f"ds_editor_{ds_name}_{st.session_state.editor_version}",
                )
                st.session_state.datasets[ds_name] = edited_ds
            else:
                # PStab 表格：卡片编辑器 + 结构预览
                card_key = state_key(ds_name)
                version_key = f"_ds_version_{ds_name}"
                if st.session_state.get(version_key) != st.session_state.editor_version:
                    st.session_state[card_key] = df_to_card_state(ds_df)
                    st.session_state[version_key] = st.session_state.editor_version

                tab_edit, tab_preview = st.tabs(["✏️ 编辑", "👁️ 结构预览"])

                with tab_edit:
                    templates = load_templates()
                    result_df = render_dataset_editor(ds_name, ds_df, templates)
                    st.session_state.datasets[ds_name] = result_df

                with tab_preview:
                    render_preview(ds_name, st.session_state.get(card_key, []))

        elif ds_name:
            st.info(f"数据表 '{ds_name}' 尚未创建，请在上方新建。")
        else:
            st.info("当前行未填写 Datasets 字段，或 MacVar=mtext 不需要数据表。")
    else:
        st.info("在主表中点击某行以编辑其对应的数据表。")

    # ── 模板管理 ────────────────────────────────────────────────────────────
    with st.expander("变量类型模板配置"):
        from templates_io import save_templates
        templates_edit = load_templates()

        st.caption("连续变量子行（Label + Aval 模板）")
        cont_tmpl = templates_edit.get("连续变量", {})
        cont_children = cont_tmpl.get("children", [])
        new_children = []
        for j, child in enumerate(cont_children):
            c1, c2, c3 = st.columns([3, 3, 0.5])
            with c1:
                lbl = st.text_input(
                    "Label", value=child.get("Label", ""),
                    label_visibility="collapsed",
                    key=f"tmpl_label_{st.session_state.tmpl_version}_{j}"
                )
            with c2:
                avl = st.text_input(
                    "Aval", value=child.get("Aval", ""),
                    label_visibility="collapsed",
                    key=f"tmpl_aval_{st.session_state.tmpl_version}_{j}"
                )
            with c3:
                if not st.button("🗑", key=f"tmpl_del_{st.session_state.tmpl_version}_{j}"):
                    new_children.append({"Label": lbl, "Aval": avl})
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

        if st.button("保存模板", key="btn_save_tmpl", type="secondary"):
            try:
                save_templates(templates_edit)
                st.cache_data.clear()  # 清除 load_templates 缓存，使新模板即时生效
                st.session_state.tmpl_version += 1
                st.success("模板已保存")
            except OSError as e:
                st.error(f"保存失败：{e}")

    # ── Config 模板管理 ──────────────────────────────────────────────────────
    cfg_tmpl_ver = st.session_state.get("cfg_tmpl_version", 0)
    with st.expander("⚙️ Config 模板配置"):
        tab_sec, tab_pop, tab_levels = st.tabs(["Section 映射", "pop 选项", "显示级别"])

        # ── Tab1: Section 映射 ────────────────────────────────────────────────
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

        # ── Tab2: pop 选项 ────────────────────────────────────────────────────
        with tab_pop:
            cfg_tmpl_pop = load_config_templates()
            pop_opts: list = list(cfg_tmpl_pop.get("pop_options", []))
            new_pop_opts: list = []
            for j, opt in enumerate(pop_opts):
                pc1, pc2 = st.columns([4, 0.5])
                with pc1:
                    new_opt = st.text_input(
                        "pop", value=opt, label_visibility="collapsed",
                        key=f"cfgtmpl_pop_{cfg_tmpl_ver}_{j}",
                    )
                with pc2:
                    if not st.button("🗑", key=f"cfgtmpl_popdel_{cfg_tmpl_ver}_{j}"):
                        if new_opt.strip():
                            new_pop_opts.append(new_opt.strip())
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

        # ── Tab3: 显示级别 ────────────────────────────────────────────────────
        with tab_levels:
            from schema import CONFIG_COLS as _ALL_COLS
            disp_cfg = load_display_levels()
            field_levels: dict = disp_cfg.get("field_levels", {})
            level_options = ["一级", "二级", "不显示"]
            level_map = {"level1": "一级", "level2": "二级", "hidden": "不显示"}
            level_rev = {"一级": "level1", "二级": "level2", "不显示": "hidden"}

            new_field_levels: dict = {}
            st.caption("字段  →  显示级别（必显示字段锁定不可修改）")
            for field in _ALL_COLS:
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

    # ── 状态栏 + 保存按钮 ───────────────────────────────────────────────────
    st.divider()

    # ── 校验状态 ─────────────────────────────────────────────────────────────
    if errors:
        for e in errors[:5]:
            st.error(str(e))
        if len(errors) > 5:
            st.warning(f"...还有 {len(errors) - 5} 条错误")
    else:
        st.success("校验通过")

    # ── 操作按钮栏 ───────────────────────────────────────────────────────────
    save_disabled = bool(errors) or not st.session_state.protocol_name.strip()
    btn_c1, btn_c2, btn_c3, btn_spacer = st.columns([1.4, 1.6, 2.0, 3])

    with btn_c1:
        if st.button("💾 保存草稿", key="btn_draft"):
            try:
                content = dump_yaml(edited_config, st.session_state.datasets,
                                    st.session_state.protocol_name or "draft")
                from renderer import _TEMP_YAML, _ensure_output_dir
                _ensure_output_dir()
                _TEMP_YAML.write_text(content, encoding="utf-8")
                st.toast(f"草稿已保存至 {_TEMP_YAML.name}")
            except Exception as e:
                st.error(f"保存草稿失败：{e}")

    with btn_c2:
        render_disabled = bool(errors)
        if st.button("🚀 生成 TFL Shell", key="btn_render",
                     disabled=render_disabled, type="secondary"):
            try:
                yaml_content = dump_yaml(
                    edited_config, st.session_state.datasets,
                    st.session_state.protocol_name or "preview"
                )
            except Exception as e:
                st.error(f"YAML 序列化失败：{e}")
                yaml_content = None

            if yaml_content:
                st.session_state.render_status["status"] = "pending"
                with st.spinner("R 正在渲染文档，请稍候（最长 5 分钟）..."):
                    result = run_render(yaml_content)

                import datetime
                fname = f"output_{datetime.datetime.now():%Y%m%d_%H%M%S}.docx"
                st.session_state.render_status.update({
                    "status": result["status"],
                    "output_bytes": result.get("output_bytes"),
                    "output_name": fname if result["status"] == "success" else None,
                    "error_log": (result.get("stderr") or "") + "\n" + (result.get("stdout") or ""),
                    "error_summary": result.get("error_summary"),
                    "seq_hint": result.get("seq_hint"),
                    "elapsed": result.get("elapsed"),
                })
                st.rerun()

    with btn_c3:
        if not st.session_state.protocol_name.strip():
            st.caption("请先填写方案简称")
        if st.button("🔒 保存并提交 Git", disabled=save_disabled,
                     type="primary", key="btn_save"):
            st.session_state.config_df = edited_config
            _do_save(git_ops)

    # ── 渲染结果区 ───────────────────────────────────────────────────────────
    rs = st.session_state.render_status
    if rs["status"] == "success":
        elapsed = rs.get("elapsed") or 0
        size_kb = len(rs["output_bytes"]) // 1024 if rs["output_bytes"] else 0
        st.success(f"✅ 渲染成功（耗时 {elapsed:.1f}s，文件大小 {size_kb} KB）")
        st.download_button(
            label="📥 下载 output.docx",
            data=rs["output_bytes"],
            file_name=rs["output_name"] or "output.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            key="btn_download",
        )

    elif rs["status"] == "error":
        elapsed = rs.get("elapsed") or 0
        summary = rs.get("error_summary") or "未知错误"
        seq_hint = rs.get("seq_hint")

        st.error(f"❌ 渲染失败（耗时 {elapsed:.1f}s）")
        st.code(f"R 错误：\n{summary}", language=None)

        if seq_hint is not None:
            if st.button(f"📍 定位到 Seq {seq_hint}", key="btn_locate_seq"):
                # 把 focus 设到对应卡片
                card_state = st.session_state.get(_CFG_CARD_KEY, [])
                target = None
                for i, c in enumerate(card_state):
                    if i + 1 == seq_hint:
                        target = c["_id"]
                        break
                if target:
                    st.session_state[_FOCUS_KEY] = target
                    st.session_state[_CARD_STATE_KEY] = _update_card(
                        card_state, target, _level="focus"
                    )
                    st.rerun()

        if rs.get("error_log"):
            with st.expander("查看 R 完整日志"):
                st.code(rs["error_log"], language=None)

    # ── YAML 预览（只读，不写 session_state）────────────────────────────────
    with st.expander("YAML 预览"):
        try:
            preview = dump_yaml(
                edited_config,
                st.session_state.datasets,
                st.session_state.protocol_name,
            )
            st.code(preview, language="yaml")
        except Exception as e:
            st.error(f"序列化失败：{e}")


def _do_save(git_ops):
    protocol = st.session_state.protocol_name.strip()
    try:
        content = dump_yaml(
            st.session_state.config_df,
            st.session_state.datasets,
            protocol,
        )
    except Exception as e:
        st.error(f"YAML 序列化失败：{e}")
        return

    rel_path = make_filename(protocol)
    msg = make_commit_msg(protocol)

    if git_ops is None:
        dest = _repo_config_dir().parent / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
        st.success(f"已保存（未配置 Git）：{dest}")
        return

    with st.spinner("正在提交 Git..."):
        try:
            saved_path = git_ops.write_and_commit(rel_path, content, msg)
            st.success(f"已保存并提交 Git（本地）：`{saved_path}`")
        except RuntimeError as e:
            st.error(str(e))
        except Exception as e:
            st.error(f"Git 操作失败：{e}")


if __name__ == "__main__":
    main()
