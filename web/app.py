"""TFL Shell 配置编辑器 —— Streamlit 入口"""
import re
import tomllib
from pathlib import Path

import pandas as pd
import streamlit as st

from excel_io import list_excel_pairs, load_excel
from git_ops import GitOps, make_commit_msg, make_filename
from schema import CONFIG_COLS
from validators import validate
from config_templates_io import load_config_templates
from config_editor import _CARD_STATE_KEY as _CFG_CARD_KEY, _FOCUS_KEY, _update_card, collect_fig_images
from renderer import run_render

from yaml_io import dump_yaml, list_yaml_files, load_yaml
from overview import render_overview
from templates_tab import render_templates_tab
from datasets_tab import render_datasets_tab
from config_tab import render_config_tab
from keys import ACTIVE_TAB as _ACTIVE_TAB_KEY, TAB_SWITCH_REQ, CFG_FOCUS_ID

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


def _plot_tool_path() -> str:
    """从 config.toml 读取画图工具路径；未配置时返回空字符串。"""
    if not CONFIG_TOML.exists():
        return ""
    with open(CONFIG_TOML, "rb") as f:
        cfg = tomllib.load(f)
    return cfg.get("plot_tool", {}).get("path", "")


# ── Session state 初始化 ────────────────────────────────────────────────────

def _empty_config() -> pd.DataFrame:
    return pd.DataFrame(columns=CONFIG_COLS)


def _init_state():
    if "config_df" not in st.session_state:
        st.session_state.config_df = _empty_config()
    if "datasets" not in st.session_state:
        st.session_state.datasets = {}
    if "selected_id" not in st.session_state:
        st.session_state.selected_id = None
    if "protocol_name" not in st.session_state:
        st.session_state.protocol_name = ""
    if "editor_version" not in st.session_state:
        st.session_state.editor_version = 0
    if "tmpl_version" not in st.session_state:
        st.session_state.tmpl_version = 0
    if "stat_tmpl_version" not in st.session_state:
        st.session_state["stat_tmpl_version"] = 0
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
    if _ACTIVE_TAB_KEY not in st.session_state:
        st.session_state[_ACTIVE_TAB_KEY] = "config"
    if "default_trtlab" not in st.session_state:
        st.session_state.default_trtlab = ""
    if "default_dutoffdate" not in st.session_state:
        st.session_state.default_dutoffdate = ""
    if "figures" not in st.session_state:
        st.session_state["figures"] = {}
    if "_plot_tool_path" not in st.session_state:
        st.session_state["_plot_tool_path"] = _plot_tool_path()


def _clear_card_state():
    """清除所有 card state 相关的 session key，避免旧编辑状态污染。"""
    stale = [k for k in st.session_state.keys()
             if k.startswith("card_state_") or k.startswith("_ds_version_")]
    for k in stale:
        del st.session_state[k]


# ── 加载辅助 ────────────────────────────────────────────────────────────────

def _extract_protocol(filename: str) -> str:
    """从 YAML 文件名提取方案简称。
    config_ISS.yaml → ISS
    config_ISS_20260601_093000.yaml → ISS（兼容旧时间戳格式）
    不符合约定的文件名（如 temp.yaml）会将完整 stem 作为方案简称回填。
    """
    # 仅对 config_*.yaml 命名约定的文件有效
    stem = Path(filename).stem          # config_ISS 或 config_ISS_20260601_093000
    body = stem.removeprefix("config_") # ISS 或 ISS_20260601_093000
    return re.sub(r"_\d{8}_\d{6}$", "", body)


def _guess_dataset_pair(cfg_name: str, ds_names: list[str]) -> str:
    """config_ISS.xlsx → datasets_ISS.xlsx（找不到则返回首个）。"""
    stem = cfg_name.removeprefix("config_").removesuffix(".xlsx")
    target = f"datasets_{stem}.xlsx"
    return target if target in ds_names else (ds_names[0] if ds_names else "")


def _do_load(loader, success_msg: str, protocol_name: str | None = None):
    """统一加载入口：调用 loader()，成功则写入 session_state 并重置编辑器。
    loader 可返回 2 元组 (config_df, datasets) 或 3 元组 (config_df, datasets, figures)。
    """
    try:
        result = loader()
        if len(result) == 3:
            cfg_df, dsets, figs = result
        else:
            cfg_df, dsets = result
            figs = {}
        st.session_state.config_df = cfg_df
        st.session_state.datasets = dsets
        st.session_state["figures"] = figs
        st.session_state.selected_id = None
        st.session_state.editor_version += 1
        if protocol_name is not None:
            st.session_state.protocol_name = protocol_name
        # 清除所有数据集的 card state，避免旧编辑状态污染新文件
        _clear_card_state()
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
                proto = _extract_protocol(selected_file)
                _do_load(
                    lambda p=config_dir / selected_file: load_yaml(p),
                    f"已加载 YAML：{selected_file}",
                    protocol_name=proto,
                )
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
            st.session_state.selected_id = None
            st.session_state.editor_version += 1
            _clear_card_state()

    # 工具栏第二行：Trtlab / Dutoffdate 统一填写
    _trtlab_presets = load_config_templates().get("trtlab_presets", [])
    _CUSTOM_TRTLAB = "✏️ 自定义"
    _preset_labels = [p["label"] for p in _trtlab_presets if p.get("label")]
    _preset_vals   = {p["label"]: p["value"] for p in _trtlab_presets if p.get("label")}

    _tb_l1, _tb_l2, _tb_l3, _tb_r1, _tb_r2 = st.columns([1.4, 2.2, 0.9, 3, 1])
    with _tb_l1:
        _sel_preset = st.selectbox(
            "Trtlab 预设",
            options=[_CUSTOM_TRTLAB] + _preset_labels,
            key="trtlab_preset_sel",
            label_visibility="visible",
        )
    with _tb_l2:
        if _sel_preset == _CUSTOM_TRTLAB:
            st.session_state.default_trtlab = st.text_input(
                "自定义 Trtlab",
                value=st.session_state.default_trtlab,
                placeholder="如 A组|B组|合计",
                key="input_default_trtlab",
            )
        else:
            _preset_v = _preset_vals.get(_sel_preset, "")
            st.session_state.default_trtlab = _preset_v
            st.text_input(
                "Trtlab（预设）",
                value=_preset_v,
                disabled=True,
                key="input_default_trtlab",
            )
    with _tb_l3:
        _sec_prefix = st.text_input(
            "限 Section",
            placeholder="如 14.1",
            key="trtlab_sec_prefix",
            help="填写后「统一替换」只更新该 Section 开头的行，留空则替换全部",
        )
        st.write("")
        if st.button("统一替换", key="btn_replace_trtlab",
                     help="将所有（或指定 Section）行的 Trtlab 替换为左侧值"):
            _rv = st.session_state.default_trtlab.strip()
            if _rv:
                _pfx = _sec_prefix.strip()
                _new_cs = []
                for _c in st.session_state.get(_CFG_CARD_KEY, []):
                    _sec_val = str(_c.get("Section no") or "")
                    if not _pfx or _sec_val.startswith(_pfx):
                        _c = dict(_c)
                        _c["Trtlab"] = _rv
                    _new_cs.append(_c)
                st.session_state[_CFG_CARD_KEY] = _new_cs
                st.session_state["_trtlab_field_ver"] = st.session_state.get("_trtlab_field_ver", 0) + 1
                st.rerun()
    with _tb_r1:
        st.session_state.default_dutoffdate = st.text_input(
            "默认 Dutoffdate（新增TFL时自动填入）",
            value=st.session_state.default_dutoffdate,
            placeholder="如 2026-06-01",
            key="input_default_dutoffdate",
        )
    with _tb_r2:
        st.write("")
        st.write("")
        if st.button("统一替换", key="btn_replace_dutoffdate", help="将所有行的 Dutoffdate 替换为上方输入值"):
            _rv2 = st.session_state.default_dutoffdate.strip()
            if _rv2:
                _new_cs2 = []
                for _c in st.session_state.get(_CFG_CARD_KEY, []):
                    _c = dict(_c)
                    _c["Dutoffdate"] = _rv2
                    _new_cs2.append(_c)
                st.session_state[_CFG_CARD_KEY] = _new_cs2
                st.session_state["_dutoffdate_field_ver"] = st.session_state.get("_dutoffdate_field_ver", 0) + 1
                st.rerun()

    # ── 标签页 ──────────────────────────────────────────────────────────────
    _active = st.session_state.get(_ACTIVE_TAB_KEY, "config")
    _tab_names = ["📋 Config章节", "🗂 Datasets", "📊 项目总览", "⚙️ 模板配置"]
    _tab_keys  = ["config",        "datasets",   "overview",   "templates"]
    _tab_index = _tab_keys.index(_active) if _active in _tab_keys else 0
    _default_tab = _tab_names[_tab_index]

    _tab_ver = st.session_state.get(TAB_SWITCH_REQ, 0)
    tab_config, tab_datasets, tab_overview, tab_templates = st.tabs(
        _tab_names, default=_default_tab, key=f"main_tabs_v{_tab_ver}"
    )

    # ── 四个标签页 ───────────────────────────────────────────────────────────
    with tab_config:
        edited_config = render_config_tab()

    with tab_datasets:
        render_datasets_tab()

    with tab_overview:
        render_overview(
            card_state=st.session_state.get(_CFG_CARD_KEY, []),
            render_status=st.session_state.render_status,
            protocol_name=st.session_state.protocol_name,
        )

    with tab_templates:
        render_templates_tab()

    errors = validate(edited_config, st.session_state.datasets)

    # ── 状态栏 + 保存按钮 ───────────────────────────────────────────────────
    st.divider()

    # ── 校验状态 ─────────────────────────────────────────────────────────────
    if errors:
        with st.expander(f"⚠️ {len(errors)} 条配置错误（点击展开）", expanded=False):
            for e in errors:
                st.error(str(e))
    else:
        st.success("校验通过")

    # ── 操作按钮栏 ───────────────────────────────────────────────────────────
    save_disabled = bool(errors) or not st.session_state.protocol_name.strip()
    btn_c1, btn_c2, btn_c3, btn_spacer = st.columns([1.4, 1.6, 2.0, 3])

    with btn_c1:
        draft_disabled = not st.session_state.protocol_name.strip()
        if draft_disabled:
            st.caption("请先填写方案简称")
        if st.button("💾 保存草稿", key="btn_draft", disabled=draft_disabled):
            try:
                # 草稿有意跳过校验错误，允许保存中间状态；数据源用 edited_config（实时）
                content = dump_yaml(
                    edited_config,
                    st.session_state.datasets,
                    st.session_state.protocol_name,
                    figures=collect_fig_images(st.session_state.get(_CFG_CARD_KEY, [])),
                )
                rel_path = make_filename(st.session_state.protocol_name)
                dest = _repo_config_dir().parent / rel_path
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(content, encoding="utf-8")
                st.success(f"草稿已保存：{dest}")
            except Exception as e:
                st.error(f"保存草稿失败：{e}")

    with btn_c2:
        render_disabled = bool(errors)
        if st.button("🚀 生成 TFL Shell", key="btn_render",
                     disabled=render_disabled, type="secondary"):
            try:
                yaml_content = dump_yaml(
                    edited_config, st.session_state.datasets,
                    st.session_state.protocol_name or "preview",
                    figures=collect_fig_images(st.session_state.get(_CFG_CARD_KEY, [])),
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

    # ── 单TFL预览结果区 ──────────────────────────────────────────────────────
    pr = st.session_state.get("preview_result")
    if pr:
        pr_title = st.session_state.get("preview_card_title", "TFL")
        if pr["status"] == "success":
            elapsed = pr.get("elapsed") or 0
            size_kb = len(pr["output_bytes"]) // 1024 if pr["output_bytes"] else 0
            st.success(f"👁 预览就绪：{pr_title}（{elapsed:.1f}s，{size_kb} KB）")
            st.download_button(
                label=f"📥 下载预览 {pr_title}.docx",
                data=pr["output_bytes"],
                file_name=f"preview_{pr_title}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                key="btn_preview_download",
            )
            if st.button("清除预览", key="btn_preview_clear"):
                del st.session_state["preview_result"]
                st.rerun()
        else:
            summary = pr.get("error_summary") or "未知错误"
            st.error(f"👁 预览失败：{summary}")
            if pr.get("error_log"):
                with st.expander("查看 R 日志"):
                    st.code(pr["error_log"], language=None)

    # ── YAML 预览（按钮触发，避免每次 rerun 序列化）────────────────────────
    _yaml_preview_key = "_yaml_preview_content"
    with st.expander("YAML 预览", expanded=False):
        if st.button("生成 YAML 预览", key="btn_yaml_preview"):
            try:
                st.session_state[_yaml_preview_key] = dump_yaml(
                    edited_config,
                    st.session_state.datasets,
                    st.session_state.protocol_name,
                    figures=collect_fig_images(st.session_state.get(_CFG_CARD_KEY, [])),
                )
            except Exception as e:
                st.session_state[_yaml_preview_key] = f"序列化失败：{e}"
        content = st.session_state.get(_yaml_preview_key, "")
        if content:
            st.code(content, language="yaml")


def _do_save(git_ops):
    protocol = st.session_state.protocol_name.strip()
    try:
        content = dump_yaml(
            st.session_state.config_df,
            st.session_state.datasets,
            protocol,
            figures=collect_fig_images(st.session_state.get(_CFG_CARD_KEY, [])),
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
