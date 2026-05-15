"""TFL Shell 配置编辑器 —— Streamlit 入口"""
import tomllib
from pathlib import Path

import pandas as pd
import streamlit as st

from excel_io import list_excel_pairs, load_excel
from git_ops import GitOps, make_commit_msg, make_filename
from schema import (
    CONFIG_COLS, CONFIG_COLS_PRIMARY, CONFIG_NUM_COLS,
    DATASET_LIST_COLS, DATASET_LIST_NUM_COLS,
    DATASET_TABLE_COLS, DATASET_TABLE_NUM_COLS,
    VALID_MACVAR, WIDE_TEXT_COLS,
)
from validators import validate
from dataset_editor import render_dataset_editor, df_to_card_state, state_key
from templates_io import load_templates
from yaml_io import dump_yaml, list_yaml_files, load_yaml

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


# ── 纯函数：合并 edited_config 到完整 df（不写 session_state）─────────────

def _merge_edited(edited: pd.DataFrame, full: pd.DataFrame, display_cols: list) -> pd.DataFrame:
    """返回合并后的新 df，不修改任何 session_state。"""
    if edited.empty:
        return _empty_config()
    out = full.copy()
    if len(edited) != len(out):
        out = out.reindex(range(len(edited)))
    for col in display_cols:
        if col in edited.columns:
            out[col] = edited[col].values
    return out


# ── column_config 构建 ──────────────────────────────────────────────────────

def _build_config_column_config(dataset_keys: list[str]) -> dict:
    cc = {}
    for col in CONFIG_COLS:
        if col in CONFIG_NUM_COLS:
            cc[col] = st.column_config.NumberColumn(col, step=1, min_value=0)
        elif col == "MacVar":
            cc[col] = st.column_config.SelectboxColumn(col, options=VALID_MACVAR)
        elif col == "Datasets":
            cc[col] = st.column_config.SelectboxColumn(
                col, options=[""] + dataset_keys
            )
        elif col in WIDE_TEXT_COLS:
            cc[col] = st.column_config.TextColumn(col, width="large")
        else:
            cc[col] = st.column_config.TextColumn(col)
    return cc


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

    # ── Config 主表 ─────────────────────────────────────────────────────────
    st.subheader("Config 主表")

    dataset_keys = list(st.session_state.datasets.keys())
    cc = _build_config_column_config(dataset_keys)
    display_cols = [c for c in CONFIG_COLS_PRIMARY if c in CONFIG_COLS]

    # key 含版本号，加载/新建时版本递增 → 编辑器以新数据干净重置
    editor_key = f"config_editor_{st.session_state.editor_version}"

    edited_config = st.data_editor(
        st.session_state.config_df[display_cols] if not st.session_state.config_df.empty
        else pd.DataFrame(columns=display_cols),
        column_config={k: cc[k] for k in display_cols if k in cc},
        num_rows="dynamic",
        width="stretch",
        key=editor_key,
    )
    # 关键：渲染过程中绝不写回 session_state.config_df，
    # 防止 data_editor 的 data 入参在两次渲染间变化导致双击问题。

    # ── 校验（直接读 edited_config）────────────────────────────────────────
    errors = validate(edited_config, st.session_state.datasets)

    # ── 行选择器（整数索引 + format_func，options 稳定不随内容变化）─────────
    if not edited_config.empty:
        def _row_label(i: int) -> str:
            r = edited_config.iloc[i]
            return f"[{r.get('SeqNum', '')}] {r.get('table no', '')}  →  {r.get('Datasets', '')}"

        sel_idx = st.selectbox(
            "选择行以编辑其数据表",
            options=list(range(len(edited_config))),
            format_func=_row_label,
            key="row_selector",
        )
        st.session_state.selected_row = sel_idx
    else:
        st.session_state.selected_row = None

    # ── Datasets 子表 ───────────────────────────────────────────────────────
    st.divider()
    st.subheader("Datasets 子表")

    sel_idx = st.session_state.selected_row
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
                # PStab 表格：卡片编辑器
                # 加载/新建时（editor_version 变化）重置 card state
                card_key = state_key(ds_name)
                version_key = f"_ds_version_{ds_name}"
                if st.session_state.get(version_key) != st.session_state.editor_version:
                    st.session_state[card_key] = df_to_card_state(ds_df)
                    st.session_state[version_key] = st.session_state.editor_version

                templates = load_templates()
                result_df = render_dataset_editor(ds_name, ds_df, templates)
                st.session_state.datasets[ds_name] = result_df

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

    # ── 状态栏 + 保存按钮 ───────────────────────────────────────────────────
    st.divider()
    col_status, col_btn = st.columns([5, 1])

    with col_status:
        if errors:
            for e in errors[:5]:
                st.error(str(e))
            if len(errors) > 5:
                st.warning(f"...还有 {len(errors) - 5} 条错误")
        else:
            st.success("校验通过")

    with col_btn:
        save_disabled = bool(errors) or not st.session_state.protocol_name.strip()
        if not st.session_state.protocol_name.strip():
            st.caption("请先填写方案简称")
        if st.button("保存并提交 Git", disabled=save_disabled, type="primary", key="btn_save"):
            # 保存时才合并 edited_config → final_config
            final_config = _merge_edited(edited_config, st.session_state.config_df, display_cols)
            st.session_state.config_df = final_config
            _do_save(git_ops)

    # ── YAML 预览（只读，不写 session_state）────────────────────────────────
    with st.expander("YAML 预览"):
        try:
            # 用临时 df 生成预览，不污染 session_state.config_df
            preview_df = _merge_edited(edited_config, st.session_state.config_df, display_cols)
            preview = dump_yaml(
                preview_df,
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
