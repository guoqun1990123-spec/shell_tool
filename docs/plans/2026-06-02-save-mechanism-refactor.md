# 保存机制重构实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 让用户可以多次编辑、每次保存，下次打开后能继续编辑同一份文件；消除时间戳文件名积累、草稿孤立、加载后需手动填方案简称等问题。

**Architecture:** 将正式文件命名从 `config_<name>_<ts>.yaml` 改为固定的 `config_<name>.yaml`（版本历史交给 Git log 管理）；「保存草稿」改为写入同一固定路径但不 commit；加载 YAML 时自动从文件名提取并回填 `protocol_name`。

**Tech Stack:** Python, Streamlit, GitPython, PyYAML

---

### Task 1: `make_filename` 去掉时间戳

**Files:**
- Modify: `web/git_ops.py:49-53`

**Step 1: 修改函数**

```python
def make_filename(protocol_name: str) -> str:
    """生成约定文件名：config_<方案简称>.yaml（同名覆盖，版本历史由 Git 保留）"""
    safe_name = protocol_name.strip().replace(" ", "_") or "unnamed"
    return f"config/config_{safe_name}.yaml"
```

同时把 `make_commit_msg` 里冗余的时间戳也去掉（commit 本身带时间，不需要重复）：

```python
def make_commit_msg(protocol_name: str) -> str:
    return f"feat(tfl): update config for {protocol_name or 'unnamed'}"
```

**Step 2: 手动验证**

在 Python shell 里确认：
```python
from git_ops import make_filename
assert make_filename("ISS") == "config/config_ISS.yaml"
assert make_filename("") == "config/config_unnamed.yaml"
assert make_filename("My Study") == "config/config_My_Study.yaml"
```

**Step 3: 运行现有测试，确认不破坏已有功能**

```bash
cd web && python -m pytest tests/ -v -k "git"
```

若无 git 相关测试，直接进下一步。

**Step 4: Commit**

```bash
git add web/git_ops.py
git commit -m "refactor(save): 文件名去掉时间戳，版本历史由 Git 保留"
```

---

### Task 2: 加载 YAML 时自动回填 `protocol_name`

**Files:**
- Modify: `web/app.py`（两处：新增辅助函数 `_extract_protocol`，修改 `_do_load` 签名及调用点）

**Step 1: 在 `_guess_dataset_pair` 前面新增辅助函数**

在 `app.py` 约第 134 行（`_guess_dataset_pair` 定义前）插入：

```python
def _extract_protocol(filename: str) -> str:
    """从 YAML 文件名提取方案简称。
    config_ISS.yaml → ISS
    config_ISS_20260601_093000.yaml → ISS（兼容旧时间戳格式）
    """
    import re
    stem = Path(filename).stem          # config_ISS 或 config_ISS_20260601_093000
    body = stem.removeprefix("config_") # ISS 或 ISS_20260601_093000
    return re.sub(r"_\d{8}_\d{6}$", "", body)
```

**Step 2: 修改 `_do_load` 签名，支持可选的 `protocol_name` 参数**

```python
def _do_load(loader, success_msg: str, protocol_name: str | None = None):
    """统一加载入口：调用 loader()，成功则写入 session_state 并重置编辑器。"""
    try:
        cfg_df, dsets = loader()
        st.session_state.config_df = cfg_df
        st.session_state.datasets = dsets
        st.session_state.selected_id = None
        st.session_state.editor_version += 1
        if protocol_name is not None:
            st.session_state.protocol_name = protocol_name
        # 清除所有数据集的 card state，避免旧编辑状态污染新文件
        _clear_card_state()
        st.success(success_msg)
    except Exception as e:
        st.error(f"加载失败：{e}")
```

**Step 3: 修改 YAML 加载调用点，传入提取的 `protocol_name`**

将 `app.py` 约第 180-182 行：

```python
            if st.button("加载", key="btn_load_yaml") and selected_file != "-- 新建空白 --":
                _do_load(lambda p=config_dir / selected_file: load_yaml(p),
                         f"已加载 YAML：{selected_file}")
```

改为：

```python
            if st.button("加载", key="btn_load_yaml") and selected_file != "-- 新建空白 --":
                proto = _extract_protocol(selected_file)
                _do_load(
                    lambda p=config_dir / selected_file: load_yaml(p),
                    f"已加载 YAML：{selected_file}",
                    protocol_name=proto,
                )
```

**Step 4: 验证**

在 Python shell 里确认辅助函数逻辑：
```python
import re
from pathlib import Path

def _extract_protocol(filename):
    stem = Path(filename).stem
    body = stem.removeprefix("config_")
    return re.sub(r"_\d{8}_\d{6}$", "", body)

assert _extract_protocol("config_ISS.yaml") == "ISS"
assert _extract_protocol("config_ISS_20260601_093000.yaml") == "ISS"
assert _extract_protocol("config_My_Study.yaml") == "My_Study"
```

**Step 5: 运行测试**

```bash
cd web && python -m pytest tests/ -v
```

**Step 6: Commit**

```bash
git add web/app.py
git commit -m "feat(save): 加载 YAML 时自动回填 protocol_name"
```

---

### Task 3: 「保存草稿」改为写固定路径，不再用 temp_render.yaml

**Files:**
- Modify: `web/app.py`（`btn_draft` 的点击处理，约第 707-716 行）

**背景：** 目前草稿写 `output/temp_render.yaml`（渲染临时文件），与正式保存路径完全不同，下次打开无法加载继续编辑。目标：草稿写 `config/config_<protocol>.yaml`（与正式保存同一路径），但不 git commit。

**Step 1: 修改草稿保存逻辑**

将现有的草稿按钮处理（约 707-716 行）：

```python
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
```

改为：

```python
    with btn_c1:
        draft_disabled = not st.session_state.protocol_name.strip()
        if st.button("💾 保存草稿", key="btn_draft", disabled=draft_disabled):
            try:
                content = dump_yaml(
                    edited_config,
                    st.session_state.datasets,
                    st.session_state.protocol_name,
                )
                rel_path = make_filename(st.session_state.protocol_name)
                dest = _repo_config_dir().parent / rel_path
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(content, encoding="utf-8")
                st.toast(f"草稿已保存：{dest.name}")
            except Exception as e:
                st.error(f"保存草稿失败：{e}")
```

注意：`_repo_config_dir()` 返回 `config/` 目录，所以 `_repo_config_dir().parent` 就是仓库根目录，`/ rel_path` 拼出 `<root>/config/config_ISS.yaml`。

**Step 2: 检查 `draft_disabled` 与现有 `save_disabled` 不冲突**

`save_disabled`（第 703 行）同时检查 errors 和 protocol_name。草稿只检查 protocol_name（草稿允许带校验错误保存）。确认逻辑不重叠，不需要改 `save_disabled`。

**Step 3: 手动端到端验证**

启动 Web 界面：
```bash
cd web && streamlit run app.py --server.port 8501
```
操作步骤：
1. 在「方案简称」填 `TEST`
2. 随便修改一个卡片字段
3. 点「保存草稿」→ 应提示 `草稿已保存：config_TEST.yaml`
4. 刷新页面（模拟下次打开）
5. 在「加载已有 YAML」里选 `config_TEST.yaml`，点「加载」
6. 确认「方案简称」自动回填为 `TEST`，卡片内容与保存前一致

**Step 4: Commit**

```bash
git add web/app.py
git commit -m "refactor(save): 草稿写入固定路径 config_<name>.yaml，支持关闭后继续编辑"
```

---

### Task 4: 补充 `list_yaml_files` 排除渲染临时文件（防御性）

**Files:**
- Modify: `web/yaml_io.py:114-120`

**背景：** `temp_render.yaml` 之前在 `output/` 目录，不会出现在 YAML 列表里。重构后渲染临时文件仍在 `output/`（`renderer.py` 的 `_TEMP_YAML` 不变），但 `config/` 目录里只有正式文件，无需特别过滤。

只需确认 `list_yaml_files` 已按修改时间倒序排列（当前代码已实现），不需要修改。

**验证：**
```python
from pathlib import Path
from yaml_io import list_yaml_files

files = list_yaml_files("../config")
# 确认最新修改的文件排在第一位
print([f.name for f in files])
```

若已正确排序，跳过此 Task，无需 commit。

---

## 变更汇总

| 文件 | 改动 |
|------|------|
| `web/git_ops.py` | `make_filename` 去掉时间戳；`make_commit_msg` 去掉时间戳 |
| `web/app.py` | 新增 `_extract_protocol`；`_do_load` 增加 `protocol_name` 参数；YAML 加载调用传入提取的名称；草稿按钮改写固定路径 |
| `web/yaml_io.py` | 仅验证，不改动 |
