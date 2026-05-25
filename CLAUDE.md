# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

基于R语言的临床试验TFL（Tables, Figures, Listings）Shell文档自动生成工具。支持从Excel或YAML配置文件读取结构，生成符合监管要求的Word文档。配套Streamlit Web界面，供统计师在浏览器中编辑配置、管理数据集、预览并一键生成文档。YAML格式专为Web界面→Git工作流设计。

## 运行方式

### R 端（直接生成）

```r
# 方式一：直接运行入口脚本（工作目录需为项目根目录）
source("run_example.R")

# 方式二：Excel输入（传统方式）
source("R/generators/generate_shell.R")
generate_shell(
  config_file   = "config/config.xlsx",
  datasets_file = "config/datasets.xlsx",
  output_file   = "output/output_shell.docx"
)

# 方式三：YAML输入（单文件，datasets_file 可省略或设为 NULL）
source("R/generators/generate_shell.R")
generate_shell(
  config_file   = "config/config_sample.yaml",
  datasets_file = NULL,
  output_file   = "output/output_shell_yaml.docx"
)
```

### Web 界面（推荐工作流）

```bat
# Windows：双击 start.bat，或在命令行运行：
streamlit run web/app.py --server.port 8501
```

**Web→Git 工作流：** 统计师在Web界面操作 → 后台生成YAML → 自动 `git commit` + push → R端调用 `generate_shell(config_file = "<yaml路径>", ...)` 渲染。
文件命名约定：`config_<方案简称>_<YYYYMMDD_HHMMSS>.yaml`

## 依赖包

### R 依赖

```r
install.packages(c("openxlsx", "officer", "flextable", "dplyr",
                   "survival", "survminer", "ggplot2", "ggpubr", "yaml"))
```

### Python 依赖（Web界面）

```bash
pip install -r web/requirements.txt
# 包含：streamlit, pyyaml, GitPython, pandas, openpyxl
```

## 架构

### R 端调用链

```
run_example.R → R/generators/generate_shell.R（主函数）→ 加载所有子模块
├── R/utils/read_config.R         # 读取config.xlsx和datasets.xlsx，统一列名
├── R/utils/read_yaml_config.R    # 读取单文件YAML，输出与read_config等价结构，含轻量校验
├── R/utils/parse_rich_text.R     # 解析上标/下标标记，生成officer富文本对象
├── R/generators/generate_table.R    # PStab表格：构建表头、处理Class分组、创建三线表
├── R/generators/generate_listing.R  # RptList清单：按Byseq提取list工作表数据
├── R/generators/generate_figure.R   # 图形：KM/游泳/瀑布/蜘蛛/折线/森林图，输出临时PNG
└── R/assemble_document.R            # 将表格/清单/图形写入Word文档，处理章节标题和脚注
```

### Web 端模块结构

```
web/
├── app.py                  # Streamlit 入口：4标签页布局 + 工具栏 + 操作按钮
├── config_editor.py        # Config章节卡片编辑器（三级显示：collapsed/level1/focus）
├── section_nav.py          # 左侧章节导航树（章节折叠/展开/筛选/视图切换）
├── section_table.py        # 章节批量编辑表格视图（表格行内编辑 + 勾选批量删除）
├── overview.py             # 项目总览（章节统计 + 快速导航 + 渲染状态）
├── dataset_editor.py       # Datasets 卡片编辑器（变量类型模板扩展）
├── dataset_preview.py      # Datasets 结构预览
├── excel_io.py             # Excel 读取（config + datasets 两文件）
├── yaml_io.py              # YAML 读取/写出（单文件格式）
├── renderer.py             # 调用 Rscript 渲染，返回 docx bytes
├── git_ops.py              # GitPython 封装：write → add → commit → push
├── validators.py           # 前端校验（与 R 端 read_yaml_config.R 对齐）
├── schema.py               # 字段定义：CONFIG_COLS, VALID_MACVAR, DATASET_*_COLS
├── config_templates_io.py  # Config 模板（Section映射/pop选项）读写
├── config_display_io.py    # 字段显示级别（level1/level2/hidden）读写
├── templates_io.py         # 变量类型模板（连续变量子行等）读写
└── config.toml             # Web 配置：Git仓库路径、远程、作者信息
```

所有 `source()` 路径均相对于项目根目录（`setwd` 在 `run_example.R` 中设置）。

## Web 界面核心设计

### 4标签页布局

| 标签 | 功能 |
|------|------|
| 📋 Config章节 | 章节导航树 + 卡片/表格视图编辑每条TFL |
| 🗂 Datasets | 选中行对应的数据集编辑器（PStab行/list行） |
| 📊 项目总览 | 章节统计表、快速导航、最近渲染状态 |
| ⚙️ 模板配置 | 变量类型模板、Section映射、pop选项、字段显示级别 |

工具栏（方案简称/加载/新建）和操作按钮（保存草稿/生成TFL/提交Git）全局可见，不进标签页。

### 卡片三级显示

- `collapsed` — 折叠态，只显示摘要行（序号、章节号、标题、MacVar等）
- `level1` — 展开态，显示主要字段 + Datasets嵌入面板 + 「展开更多」expander
- `focus` — 专注模式，全屏显示单张卡片，其余卡片隐藏

### 章节视图切换

左侧导航树每个章节节点右侧有「表格」按钮，点击后右侧切换为该章节的批量编辑表格视图（section_table.py）。表格中点击标题列按钮可跳转到该卡片的focus模式。

### session_state 关键 Key

| Key | 类型 | 说明 |
|-----|------|------|
| `config_card_state` | `list[dict]` | Config 主表所有卡片数据 |
| `section_nav_view_mode` | `str` | `"card"` \| `"table"` |
| `section_nav_table_section` | `str` | 当前表格视图的章节号 |
| `section_nav_filter` | `dict` | `{section, scroll_to}` 筛选状态 |
| `_cfg_focus_id` | `str\|None` | 当前focus卡片的id |
| `active_tab` | `str` | `"config"` \| `"datasets"` \| `"overview"` \| `"templates"` |
| `datasets` | `dict[str, DataFrame]` | 所有数据集 |
| `render_status` | `dict` | 最近渲染状态（status/output_bytes/elapsed等） |

## 关键设计约定

**列名处理：** `openxlsx` 读取Excel时将空格转为点号，`read_config.R` 会自动还原，并做旧列名兼容映射（如 `Datesets` → `Datasets`，`Subgrop` → `Subgrp`）。

**MacVar类型决定生成逻辑：**
- `PStab` → 表格（generate_table.R）
- `RptList` → 清单（generate_listing.R）
- `mtext` → 引用已有表格，输出"格式同表XX"
- `KMplot / Swimplot / WaterfallPlot / Spiderplot / Seriesplot / Forestplot` → 图形（generate_figure.R）

**三线表格式：** 所有表格统一使用 `border_remove()` 后只加顶部、表头下方、底部三条1.5pt线。字体：中文宋体 + 英文Times New Roman，10.5pt。

**多级表头：** `Trtlab` 用 `|` 分隔治疗组，`Subgrp` 用 `|` 分隔子组。有子组时用 `set_header_df` 构建两行表头，治疗组跨列合并。

**Class分组：** `build_table_data` 检测相邻行的 `Class` 变化，自动插入空行。

**图形输出：** 图形函数返回临时PNG路径，`assemble_document.R` 插入后调用 `unlink()` 删除临时文件。

**富文本标记语法：** Excel / Web 中可在 Label、脚注、Labparm 等任意文本字段使用以下标记：
- `^[文字]` → 上标，如 `IC50^[a]` 显示为 IC50ᵃ
- `_[文字]` → 下标，如 `H_[2]O` 显示为 H₂O
- `[文字]` 普通方括号直接写即可，不会被解析（只有 `^[` 和 `_[` 触发特殊格式）

实现位于 `R/utils/parse_rich_text.R`，核心函数：
- `parse_rich_text_chunks(text)` — 将文本拆分为普通/上标/下标 chunk 列表
- `parse_rich_text_to_fpar(text, base_prop)` — 返回 officer `fpar` 对象，用于段落
- `parse_rich_text_to_paragraph(text, base_size)` — 返回 flextable `as_paragraph` 对象，用于单元格
- `has_rich_text(text)` — 快速判断是否含标记（用于条件分支避免不必要的解析）

`assemble_document.R` 中 `body_add_rich_par()` 统一封装了段落渲染：含标记时自动切换到 `body_add_fpar`，否则用 `body_add_par`。

## 输入文件规范

**config/config.xlsx** 关键列：`Section no`, `table no`, `title`, `pop`, `MacVar`, `Datasets`, `Trtlab`, `Subgrp`, `Adcols`, `Varlab`, `footnote1-7`, `PgmNotes`, `SeqNum`（排序用）

**config/datasets.xlsx** 表格型工作表列：`Class`, `Label`, `Order`（缩进0-5）, `Aval`, `exclude`（1=不显示）, `BlankCol`（如"1|2|3"）；清单用 `list` 工作表，列：`ListName`, `Byseq`, `Byorder`, `Lvalable`

**config/\*.yaml（YAML格式，与上述两个Excel等价）：**

```yaml
version: 1
config:
  - SeqNum: 1
    "Section no": "11.1"
    "table no": "14.1.1"
    MacVar: "PStab"       # PStab / RptList / mtext / KMplot / Swimplot / WaterfallPlot / Spiderplot / Seriesplot / Forestplot
    Datasets: "t_demo"    # 对应 datasets 下的键名
    Trtlab: "A组|B组|合计"
    footnote1: "脚注支持富文本 ^[上标] _[下标]"
    # ... 其余字段同 config.xlsx 列名
datasets:
  t_demo:                 # 键名 = Excel sheet名
    - {Class: "", Label: "年龄", Order: 0, Aval: "Mean (SD)", exclude: 0, BlankCol: ""}
  list:                   # MacVar=RptList 时必须存在
    - {ListName: "l_x", Byseq: 1, Byorder: 1, Lvalable: "字段标签"}
```

完整样例见 `config/config_sample.yaml`。

**templates/template.docx：** 定义页眉、页脚、页面方向（横向A4）和Word样式，`generate_shell.R` 用 `read_docx()` 加载。

## Web 端配置（config.toml）

首次使用前修改 `web/config.toml`：

```toml
[git]
repo_path    = "d:/shell_tool"      # 本地仓库根目录
remote       = "origin"
branch       = "main"
author_name  = "张三"
author_email = "zhangsan@example.com"
```

未配置时，「保存并提交 Git」按钮仍可使用，文件写入本地但不推送远程。

## 测试

```bash
cd web && python -m pytest tests/ -v
# 39个单元测试（config_editor / dataset_editor / overview 纯函数）
```
