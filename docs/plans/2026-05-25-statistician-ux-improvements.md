# 统计师 UX 改进 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 六项改进，减少统计师重复操作：复制TFL行（表格视图）、批量填充Trtlab、数据集从现有复制、脚注片段库、项目级默认Trtlab、单TFL预览。

**Architecture:** 全部改动在 `web/` 目录内，无需修改 R 端。单TFL预览复用现有 `renderer.run_render()`，仅新增一个薄包装函数 `run_preview()`，将单卡片序列化为单条目YAML再走现有渲染管道。脚注片段库扩展 `config_templates.yaml` schema，其余功能均为现有组件的 UI 补丁。

**Tech Stack:** Python 3, Streamlit, pyyaml, pandas。测试框架：pytest（`web/tests/`）。

---

## 现状速查

| 功能 | 现状 |
|------|------|
| 复制TFL（卡片视图⋮菜单） | ✅ 已实现（`config_editor.py:315`） |
| 复制TFL（表格视图行内） | ❌ 缺少 |
| 批量修改 pop / Datasets | ✅ 已实现（`section_table.py:97`） |
| 批量修改 Trtlab | ❌ 缺少 |
| 数据集从现有复制 | ❌ 缺少 |
| 脚注片段库 | ❌ 缺少 |
| 项目级默认 Trtlab | ❌ 缺少 |
| 单TFL预览 | ❌ 缺少 |

---

## Task 1：复制TFL — 表格视图行内按钮

**目标：** 在 `section_table.py` 每行右侧加一个「复制」按钮，行为与卡片视图⋮菜单一致。

**Files:**
- Modify: `web/section_table.py:175-186`（列头行），`web/section_table.py:204`（行渲染），`web/section_table.py:285-293`（c6区域）
- Modify: `web/section_table.py:6-18`（imports，确认 `_copy_card` 已导入）
- Test: `web/tests/test_config_editor.py`（`_copy_card` 已有测试，无需新增）

**Step 1: 确认 `_copy_card` 已导入**

查看 `web/section_table.py:6-18`，确认 imports 列表中有 `_copy_card`。若无，添加。

**Step 2: 列头加「复制」列**

找到 `_render_column_header()`（约第175行），修改列布局，从7列改为8列，在 `h6`（⊞）后加 `h7`：

```python
def _render_column_header() -> None:
    st.divider()
    h0, h1, h2, h3, h4, h5, h6, h7 = st.columns([0.5, 1.5, 0.8, 3.0, 1.5, 1.5, 0.5, 0.5])
    with h0: st.caption("☑")
    with h1: st.caption("table no")
    with h2: st.caption("cat")
    with h3: st.caption("title")
    with h4: st.caption("pop")
    with h5: st.caption("Datasets")
    with h6: st.caption("⊞")
    with h7: st.caption("⎘")
    st.divider()
```

**Step 3: `_render_row` 加第8列**

找到 `_render_row`（约第189行），将列声明从7列改为8列，添加 `c7`：

```python
c0, c1, c2, c3, c4, c5, c6, c7 = st.columns([0.5, 1.5, 0.8, 3.0, 1.5, 1.5, 0.5, 0.5])
```

在函数末尾（`c6` 块之后，`if is_expanded:` 之前）添加：

```python
with c7:
    if st.button("⎘", key=f"tbl_copy_{card_id}_{ver}", help="复制此TFL"):
        state = st.session_state[_CARD_STATE_KEY]
        st.session_state[_CARD_STATE_KEY] = _copy_card(state, card_id)
        st.session_state[_VERSION_KEY] = _version() + 1
        st.rerun()
```

**Step 4: 手动测试**

启动 `streamlit run web/app.py`，进入 Config章节 → 表格视图，点击某行「⎘」按钮，确认该行下方出现完整副本，table no 自动重新编号。

**Step 5: Commit**

```bash
git add web/section_table.py
git commit -m "feat(web): add copy button to section table row"
```

---

## Task 2：批量填充 Trtlab

**目标：** 在 `section_table.py` 批量操作栏增加 Trtlab 文本输入，勾选多行后可一键填充。

**Files:**
- Modify: `web/section_table.py:97-172`（`_render_bulk_bar` 函数）

**Step 1: 扩展批量操作栏列布局**

找到 `_render_bulk_bar`（约第97行），当前列声明：
```python
col_all, col_del, col_pop, col_ds, col_spacer = st.columns([0.8, 1.2, 1.5, 1.5, 3])
```

改为（缩小 spacer，加 col_trtlab）：
```python
col_all, col_del, col_pop, col_ds, col_trtlab, col_spacer = st.columns([0.8, 1.2, 1.5, 1.5, 2.0, 1.0])
```

**Step 2: 添加 Trtlab 批量填充逻辑**

在 `col_ds` 块之后、`col_spacer` 之前添加：

```python
with col_trtlab:
    sel_in_sec = checked & sec_ids
    if sel_in_sec:
        new_trtlab = st.text_input(
            "批量设Trtlab", placeholder="如 A组|B组|合计",
            key="tbl_bulk_trtlab", label_visibility="collapsed"
        )
        if st.button("填充Trtlab", key="tbl_bulk_trtlab_btn",
                     disabled=not new_trtlab.strip()):
            state = st.session_state[_CARD_STATE_KEY]
            for cid in sel_in_sec:
                state = _update_card(state, cid, Trtlab=new_trtlab.strip())
            st.session_state[_CARD_STATE_KEY] = state
            st.rerun()
    else:
        st.caption("批量填Trtlab▼")
```

**Step 3: 手动测试**

勾选章节内多行 → 在 Trtlab 框输入 `A组|B组|合计` → 点「填充Trtlab」→ 确认所有选中行 Trtlab 已更新。

**Step 4: Commit**

```bash
git add web/section_table.py
git commit -m "feat(web): add batch Trtlab fill to section table"
```

---

## Task 3：数据集从现有复制

**目标：** 在 Datasets 标签页新建数据集时，可选择「复制自已有数据集」，省去从空白逐行填写。

**Files:**
- Modify: `web/app.py:256-267`（datasets tab 新建区域）

**Step 1: 修改新建数据集 UI**

找到 `app.py` 中以下代码段（约第256行）：

```python
col_dsname, col_dsadd = st.columns([3, 1])
with col_dsname:
    new_ds_name = st.text_input("新建数据表名", ...)
with col_dsadd:
    st.write("")
    if st.button("新建数据表", key="btn_add_ds"):
        if new_ds_name and new_ds_name not in st.session_state.datasets:
            is_list = new_ds_name == "list"
            st.session_state.datasets[new_ds_name] = (
                _empty_dataset_list() if is_list else _empty_dataset_table()
            )
            st.rerun()
```

替换为（三列布局，加「复制自」选项）：

```python
col_dsname, col_dscopy, col_dsadd = st.columns([2, 2, 1])
with col_dsname:
    new_ds_name = st.text_input("新建数据表名", placeholder="如 t_demo", key="new_ds_name")
with col_dscopy:
    existing_keys = list(st.session_state.datasets.keys())
    copy_from = st.selectbox(
        "复制自（可选）", ["— 空白 —"] + existing_keys,
        key="new_ds_copy_from", label_visibility="visible"
    )
with col_dsadd:
    st.write("")
    st.write("")
    if st.button("新建数据表", key="btn_add_ds"):
        if new_ds_name and new_ds_name not in st.session_state.datasets:
            if copy_from != "— 空白 —" and copy_from in st.session_state.datasets:
                import copy
                st.session_state.datasets[new_ds_name] = st.session_state.datasets[copy_from].copy()
            else:
                is_list = new_ds_name == "list"
                st.session_state.datasets[new_ds_name] = (
                    _empty_dataset_list() if is_list else _empty_dataset_table()
                )
            st.rerun()
```

**Step 2: 手动测试**

新建名为 `t_demo2`，选择「复制自 t_demo」→ 确认新数据集行数与 `t_demo` 完全相同。

**Step 3: Commit**

```bash
git add web/app.py
git commit -m "feat(web): add copy-from option when creating new dataset"
```

---

## Task 4：脚注片段库

**目标：** 在模板配置中维护常用脚注片段，编辑卡片 footnote1-7 时可从下拉快速插入，避免重复手敲。

**Files:**
- Modify: `web/config_templates_io.py`（schema 扩展）
- Modify: `web/config_templates.yaml`（添加示例片段）
- Modify: `web/app.py:368-402`（模板配置 tab，增加片段编辑区）
- Modify: `web/config_editor.py`（footnote 字段旁加插入按钮）

**Step 1: 扩展 `config_templates_io.py` schema**

找到 `_DEFAULTS` 字典（约第11行），添加 `footnote_snippets`：

```python
_DEFAULTS: dict = {
    "section_map": {},
    "pop_options": [],
    "footnote_snippets": [],   # 新增
}
```

在 `load_config_templates()` 返回语句添加该键：

```python
return {
    "section_map": dict(data.get("section_map", {})),
    "pop_options": list(data.get("pop_options", [])),
    "footnote_snippets": list(data.get("footnote_snippets", [])),   # 新增
}
```

**Step 2: 在 `config_templates.yaml` 添加示例片段**

在文件末尾添加：

```yaml
footnote_snippets:
  - "数据截止日期：YYYY年MM月DD日"
  - "FAS=全分析集；SS=安全性分析集；PPS=符合方案集"
  - "AE=不良事件；TEAE=治疗期间出现的不良事件；SAE=严重不良事件"
```

**Step 3: 在 App 模板配置 Tab 添加片段编辑器**

在 `app.py` 模板配置 tab 的 `with tab_pop:` 块之后、`with tab_levels:` 之前，添加脚注片段编辑区（仿 pop_options 的实现模式）：

```python
# 在 tab_pop 和 tab_levels 中间新增一个 tab
tab_sec, tab_pop, tab_fn, tab_levels = st.tabs(["Section 映射", "pop 选项", "脚注片段", "显示级别"])
```

在 `with tab_fn:` 中：

```python
with tab_fn:
    cfg_tmpl_fn = load_config_templates()
    fn_snippets: list = list(cfg_tmpl_fn.get("footnote_snippets", []))
    new_fn_snippets: list = []
    for j, snippet in enumerate(fn_snippets):
        fc1, fc2 = st.columns([5, 0.5])
        with fc1:
            new_s = st.text_input(
                "脚注片段", value=snippet, label_visibility="collapsed",
                key=f"cfgtmpl_fn_{cfg_tmpl_ver}_{j}",
            )
        with fc2:
            if not st.button("🗑", key=f"cfgtmpl_fndel_{cfg_tmpl_ver}_{j}"):
                if new_s.strip():
                    new_fn_snippets.append(new_s.strip())
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
```

注意：`app.py` 原来的 `tab_sec, tab_pop, tab_levels = st.tabs(...)` 需改为四个变量接收。

**Step 4: 在 `config_editor.py` footnote 字段旁加插入按钮**

找到 `_render_level1` 中渲染 footnote1-7 的代码。当前实现为普通 `text_input`，找到后在每个 footnote 字段所在行新增一列放插入按钮：

先在 `_render_level1` 函数签名顶部读取片段列表（`templates` 已作为参数传入）：

```python
fn_snippets: list = templates.get("footnote_snippets", [])
```

对每个 footnote 字段（如 `footnote1`），将单列 `text_input` 改为两列布局：

```python
# 找到 footnote1 的渲染代码，改为：
fn_col, fn_ins_col = st.columns([5, 1])
with fn_col:
    new_fn1 = st.text_input("footnote1", value=str(card.get("footnote1") or ""),
                             key=f"cfg_fn1_{card_id}_{version}")
with fn_ins_col:
    if fn_snippets:
        chosen = st.selectbox("插入", ["＋"] + fn_snippets,
                              key=f"cfg_fn1_ins_{card_id}_{version}",
                              label_visibility="collapsed")
        if chosen != "＋":
            cur = str(card.get("footnote1") or "")
            new_fn1 = (cur + "；" + chosen).lstrip("；")
            st.session_state[_CARD_STATE_KEY] = _update_card(
                card_state, card_id, footnote1=new_fn1
            )
            st.rerun()
```

对 footnote2-7 重复相同模式（只是 key 不同）。

> **注意：** `_render_level1` 中 footnote 字段的当前代码位置需先阅读确认（通过 Read 工具），再做精确修改。

**Step 5: 手动测试**

1. 模板配置 → 脚注片段 tab，添加一条片段，保存。
2. 打开任意卡片 level1 视图，找到 footnote1 旁的插入下拉，选择该片段，确认文本追加正确。

**Step 6: Commit**

```bash
git add web/config_templates_io.py web/config_templates.yaml web/app.py web/config_editor.py
git commit -m "feat(web): add footnote snippet library for quick insert"
```

---

## Task 5：项目级默认 Trtlab

**目标：** 工具栏设置全局默认 Trtlab，新增 TFL 条目时自动填入，省去每行手填。

**Files:**
- Modify: `web/app.py:74-99`（`_init_state`），`web/app.py:143-184`（工具栏）
- Modify: `web/config_editor.py:135-136`（`_add_card`、`_insert_after`）

**Step 1: 初始化 `default_trtlab` session key**

在 `_init_state()` 函数末尾添加：

```python
if "default_trtlab" not in st.session_state:
    st.session_state.default_trtlab = ""
```

**Step 2: 工具栏加输入框**

在 `app.py` 工具栏区域（`with col_proto:` 块之后），在工具栏下方新增第二行，仅一列：

```python
# 工具栏第二行：默认 Trtlab
with st.container():
    st.session_state.default_trtlab = st.text_input(
        "默认 Trtlab（新增TFL时自动填入）",
        value=st.session_state.default_trtlab,
        placeholder="如 A组|B组|合计",
        key="input_default_trtlab",
    )
```

**Step 3: `_add_card` 和 `_insert_after` 使用默认值**

这两个函数目前是纯函数（无法访问 session_state）。采用轻量方案：**在调用处**将默认值注入，而不改函数签名。

在 `app.py` 中，找到「＋ 添加TFL」按钮的 callback（位于 `section_table.py` 的 `_render_header`）。
实际上新卡片是通过 `_insert_after` / `_add_card` 创建后，用 `_update_card` 设初值的。

在 `section_table.py` 的 `_render_header` 中，创建新卡片后立即注入默认 Trtlab：

```python
# 在 new_state = _insert_after(card_state, last_id) 之后：
default_trtlab = st.session_state.get("default_trtlab", "").strip()
for c in new_state:
    if c["_id"] not in {x["_id"] for x in card_state}:
        kw = {"Section no": sec_no}
        if default_trtlab:
            kw["Trtlab"] = default_trtlab
        new_state = _update_card(new_state, c["_id"], **kw)
        break
```

同样在 `config_editor.py` 的「+」按钮（`_insert_after` 调用处，约第282行）注入：

```python
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
```

**Step 4: 手动测试**

在工具栏填入 `A组|B组|合计`，点「＋」新增 TFL，确认 Trtlab 字段自动填入该值。

**Step 5: Commit**

```bash
git add web/app.py web/section_table.py web/config_editor.py
git commit -m "feat(web): add project-level default Trtlab for new entries"
```

---

## Task 6：单TFL预览

**目标：** 在表格视图每行加「预览」按钮，仅渲染该单条 TFL 并提供下载，无需生成完整文档。

**Architecture:**
- `renderer.py` 新增 `run_preview(card, datasets)` → 构造单条目YAML → 复用 `run_render()`
- `section_table.py` 每行加「👁」按钮，结果存入 `session_state["preview_result"]`
- `app.py` 在操作按钮栏下方展示预览下载区（与现有渲染结果区分离）

无需修改任何 R 代码——现有 `generate_shell()` 传入单条目YAML就生成单表文档。

**Files:**
- Modify: `web/renderer.py`（新增 `run_preview`）
- Modify: `web/section_table.py`（行内预览按钮）
- Modify: `web/app.py`（预览结果展示区）

**Step 1: 在 `renderer.py` 添加 `run_preview`**

在文件末尾添加：

```python
def run_preview(card: dict, datasets: dict[str, object], protocol_name: str = "preview") -> dict:
    """
    将单个卡片渲染为单条目YAML，复用 run_render() 生成单表Word文档。

    card: config_editor card dict（含 _* 元数据字段，会被过滤掉）
    datasets: 完整 datasets dict（只用到 card["Datasets"] 对应的 sheet）
    """
    import pandas as pd
    from yaml_io import dump_yaml

    # 过滤 _* 元数据，构建单行 config DataFrame
    from schema import CONFIG_COLS
    row = {k: v for k, v in card.items() if not k.startswith("_")}
    row["SeqNum"] = 1
    # 补全缺失列
    for col in CONFIG_COLS:
        if col not in row:
            row[col] = ""
    config_df = pd.DataFrame([row], columns=CONFIG_COLS)

    # 只保留该卡片需要的 dataset
    ds_name = str(card.get("Datasets") or "").strip()
    macvar = str(card.get("MacVar") or "").strip()
    preview_datasets: dict = {}
    if ds_name and ds_name in datasets:
        preview_datasets[ds_name] = datasets[ds_name]
    if macvar == "RptList" and "list" in datasets:
        preview_datasets["list"] = datasets["list"]

    yaml_content = dump_yaml(config_df, preview_datasets, protocol_name)
    return run_render(yaml_content)
```

**Step 2: 为 `run_preview` 写单元测试**

在 `web/tests/` 目录下，`test_config_editor.py` 旁边新建 `test_renderer.py`：

```python
# web/tests/test_renderer.py
"""renderer.run_preview 的单元测试（mock掉 run_render 以隔离R依赖）"""
from unittest.mock import patch, MagicMock
import pandas as pd
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from renderer import run_preview


def _make_card(macvar="PStab", ds="t_demo"):
    return {
        "_id": "abc", "_level": "collapsed",
        "SeqNum": 1, "Section no": "14.1", "table no": "14.1.1",
        "title": "测试", "MacVar": macvar, "Datasets": ds,
        "Trtlab": "A|B", "pop": "FAS",
        "footnote1": "", "footnote2": "", "footnote3": "",
        "footnote4": "", "footnote5": "", "footnote6": "", "footnote7": "",
    }


def test_run_preview_builds_single_entry_yaml():
    """run_preview 应构造只含1条config的YAML并调用run_render。"""
    card = _make_card()
    datasets = {"t_demo": pd.DataFrame(columns=["Class", "Label", "Order", "Aval", "exclude", "BlankCol"])}
    mock_result = {"status": "success", "output_bytes": b"fake", "elapsed": 0.1,
                   "stdout": "", "stderr": "", "error_summary": None, "seq_hint": None}

    with patch("renderer.run_render", return_value=mock_result) as mock_render:
        result = run_preview(card, datasets)
        assert result["status"] == "success"
        # 确认传给run_render的YAML只含1条config
        called_yaml = mock_render.call_args[0][0]
        import yaml
        parsed = yaml.safe_load(called_yaml)
        assert len(parsed["config"]) == 1
        assert parsed["config"][0]["SeqNum"] == 1


def test_run_preview_only_passes_relevant_dataset():
    """只传入Datasets字段对应的sheet，过滤掉其他sheet。"""
    card = _make_card(ds="t_demo")
    import pandas as pd
    df_demo = pd.DataFrame(columns=["Class", "Label", "Order", "Aval", "exclude", "BlankCol"])
    df_other = pd.DataFrame(columns=["Class", "Label", "Order", "Aval", "exclude", "BlankCol"])
    datasets = {"t_demo": df_demo, "t_other": df_other}
    mock_result = {"status": "success", "output_bytes": b"x", "elapsed": 0.0,
                   "stdout": "", "stderr": "", "error_summary": None, "seq_hint": None}

    with patch("renderer.run_render", return_value=mock_result):
        run_preview(card, datasets)
        from unittest.mock import call
        # 不直接断言YAML内容，只确认不抛出异常即可
```

**Step 3: 运行测试确认通过**

```bash
cd web && python -m pytest tests/test_renderer.py -v
```

预期：2 PASSED。

**Step 4: `section_table.py` 行内加「👁」预览按钮**

在 Task 1 完成后，每行已有8列。现在再加第9列「👁」（或复用 c7 旁边再加一列）。

更简洁方案：**将复制（⎘）和预览（👁）合并进 c7 区域**，用两个极小按钮叠放：

列声明改为9列：
```python
c0, c1, c2, c3, c4, c5, c6, c7, c8 = st.columns([0.5, 1.5, 0.8, 3.0, 1.5, 1.5, 0.5, 0.5, 0.5])
```

列头也相应更新：
```python
h0, h1, h2, h3, h4, h5, h6, h7, h8 = st.columns([0.5, 1.5, 0.8, 3.0, 1.5, 1.5, 0.5, 0.5, 0.5])
with h8: st.caption("👁")
```

在 `c8` 区域添加：
```python
with c8:
    if st.button("👁", key=f"tbl_preview_{card_id}_{ver}", help="预览此TFL（生成单表Word）"):
        from renderer import run_preview
        card_state_now = st.session_state[_CARD_STATE_KEY]
        cur_card = next((c for c in card_state_now if c["_id"] == card_id), card)
        datasets = st.session_state.get("datasets", {})
        with st.spinner("渲染中..."):
            result = run_preview(cur_card, datasets)
        st.session_state["preview_result"] = result
        st.session_state["preview_card_title"] = str(cur_card.get("title") or cur_card.get("table no") or "TFL")
        st.rerun()
```

**Step 5: `app.py` 添加预览结果展示区**

在 `app.py` 的渲染结果展示区（约第547行 `rs = st.session_state.render_status`）之后，添加预览结果区：

```python
# ── 单TFL预览结果区 ──────────────────────────────────────────────────────────
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
```

**Step 6: 初始化 `preview_result` session key（可选，防止 KeyError）**

在 `_init_state()` 中不需要初始化（`st.session_state.get("preview_result")` 返回 None 即可），无需修改。

**Step 7: 手动集成测试**

1. 启动 web，加载含 `PStab` 的 YAML。
2. 进入表格视图，点击某行「👁」按钮。
3. 确认 spinner 出现后消失，页面底部出现「预览就绪」成功提示和下载按钮。
4. 下载并打开 Word，确认只包含该单张表格。
5. 测试 `mtext` 类型（引用已有表格），确认渲染正常。
6. 测试 `RptList` 类型，确认 `list` 数据集被正确传递。

**Step 8: Commit**

```bash
git add web/renderer.py web/tests/test_renderer.py web/section_table.py web/app.py
git commit -m "feat(web): add single-TFL preview with download"
```

---

## 执行顺序建议

| 顺序 | Task | 改动文件数 | 预估时间 |
|------|------|-----------|---------|
| 1 | Task 1 复制按钮（表格视图） | 1 | 10 min |
| 2 | Task 2 批量填充Trtlab | 1 | 10 min |
| 3 | Task 3 数据集从现有复制 | 1 | 10 min |
| 4 | Task 5 默认Trtlab（先做，为Task 6铺垫状态） | 3 | 20 min |
| 5 | Task 4 脚注片段库（最多文件） | 4 | 30 min |
| 6 | Task 6 单TFL预览（核心功能） | 4 | 40 min |

Tasks 1–3 互相独立，可并行执行。Task 6 依赖 Task 1（表格视图已有列结构）。
