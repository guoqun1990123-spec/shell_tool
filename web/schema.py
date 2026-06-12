# 字段定义 —— 与 R/utils/read_yaml_config.R 严格对齐
# 修改此处时同步更新 R 端 .VALID_MACVAR 和 known_cols

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional

VALID_MACVAR = [
    "", "PStab", "RptList", "mtext",
    "KMplot", "Swimplot", "WaterfallPlot",
    "Spiderplot", "Seriesplot", "Forestplot",
]

# 图形类 MacVar 集合（供 UI 判断哪些行显示画图工具入口）
FIGURE_MACVARS = {"KMplot", "Swimplot", "WaterfallPlot", "Spiderplot", "Seriesplot", "Forestplot"}

REQUIRED_COLS = ["SeqNum", "Section no", "MacVar"]

# config 行的全部已知列，顺序决定主表列序
CONFIG_COLS = [
    "SeqNum", "Section no", "Section title", "cat", "table no",
    "title", "pop", "MacVar", "Datasets", "Trtlab", "Subgrp",
    "Adcols", "Varlab", "Labparm",
    "footnote1", "footnote2", "footnote3", "footnote4",
    "footnote5", "footnote6", "footnote7",
    "PgmNotes", "ByseqL", "RefTFL", "Dutoffdate", "Source_Data", "FigTemplate",
]

# 主表优先展示的列（其余列折叠到右侧）
CONFIG_COLS_PRIMARY = [
    "SeqNum", "Section no", "Section title", "cat", "table no",
    "title", "pop", "MacVar", "Datasets", "Trtlab", "Subgrp",
    "Adcols", "Varlab", "Labparm",
    "footnote1", "footnote2", "footnote3", "footnote4",
    "footnote5", "footnote6", "footnote7",
    "Source_Data", "PgmNotes", "ByseqL", "RefTFL", "Dutoffdate",
]

# 数字列（不应存为字符串）
CONFIG_NUM_COLS = {"SeqNum"}

# datasets 表格 sheet 列定义
DATASET_TABLE_COLS = ["Class", "Label", "Order", "Aval", "exclude", "BlankCol",
                      "Drug", "Visit", "Base"]
DATASET_TABLE_NUM_COLS = {"Order", "exclude"}

# list sheet 列定义（MacVar=RptList 使用）
DATASET_LIST_COLS = ["ListName", "Byseq", "Byorder", "Lvalable", "Values", "Merge", "exclude"]
DATASET_LIST_NUM_COLS = {"Byseq", "Byorder", "exclude"}

# 主表列宽提示（给 column_config 用）
WIDE_TEXT_COLS = {"title", "footnote1", "footnote2", "footnote3",
                  "footnote4", "footnote5", "footnote6", "footnote7",
                  "PgmNotes", "Trtlab"}

# 变量类型（Datasets 卡片编辑器用）
VAR_TYPES = [
    "手动输入",
    "连续变量",
    "分类变量-有子分类",
    "分类变量-无子分类",
    "日期变量",
]
VAR_TYPE_DEFAULT = "手动输入"


# ── 统计量格式数据结构（疗效终点模板用）────────────────────────────────────────

@dataclass
class StatItem:
    item_id: str
    label: str
    aval_template: str
    aval_options: List[str] = field(default_factory=list)
    special_values: List[str] = field(default_factory=list)
    unit_hint: Optional[str] = None
    default_checked: bool = True
    has_children: bool = False
    children_template: List[Dict] = field(default_factory=list)


@dataclass
class Subgroup:
    subgroup_id: str
    subgroup_name: str
    default_expanded: bool = True
    items: List[StatItem] = field(default_factory=list)


@dataclass
class EndpointGroup:
    group_id: str
    group_name: str
    icon: str = ""
    description: str = ""
    subgroups: List[Subgroup] = field(default_factory=list)


# 运行时由 templates_io.load_statistical_formats() 填充
STATISTICAL_FORMAT_GROUPS: List[EndpointGroup] = []
VALIDATION_RULES: Dict[str, str] = {}
