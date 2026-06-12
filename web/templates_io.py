"""变量类型模板 + 统计量格式模板的加载/保存，读写 web/variable_templates.yaml。"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml
import streamlit as st

import schema as _schema
from schema import EndpointGroup, StatItem, Subgroup

_TEMPLATE_FILE = Path(__file__).parent / "variable_templates.yaml"

# 内置基础类型（固定顺序，不可删除）
_BASE_TYPES = ["手动输入", "连续变量", "分类变量-有子分类", "分类变量-无子分类", "日期变量"]

_DEFAULT: dict = {
    "连续变量": {
        "children": [
            {"Label": "例数", "Aval": "xx"},
            {"Label": "均值（标准差）", "Aval": "xx.x (xx.xx)"},
            {"Label": "中位数", "Aval": "xx.x"},
            {"Label": "最小值 - 最大值", "Aval": "xx – xx"},
        ]
    },
    "分类变量-有子分类": {
        "children": [],
        "aval_options": ["xx (xx.x)"],
    },
    "分类变量-无子分类": {"aval": "xx (xx.x)"},
    "日期变量": {"aval": "YYYY-MM-DD", "children": []},
    "手动输入": {},
}


# ── 变量结构模板（基线特征表用）───────────────────────────────────────────────

@st.cache_data(ttl=60)
def load_structure_templates() -> dict:
    """加载变量结构模板，文件不存在时返回内置默认值。"""
    if not _TEMPLATE_FILE.exists():
        return _DEFAULT
    with open(_TEMPLATE_FILE, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    tmpl_raw = raw.get("templates")
    if isinstance(tmpl_raw, list):
        # version 2 列表格式：[{type: "连续变量", children: [...], ...}]
        data = {}
        for item in tmpl_raw:
            t = item.get("type")
            if t:
                data[t] = {k: v for k, v in item.items() if k != "type"}
    elif isinstance(tmpl_raw, dict):
        data = tmpl_raw
    else:
        # 旧格式：无 templates 键，type 名直接作为根键
        data = {
            k: v for k, v in raw.items()
            if k not in ("version", "statistical_formats", "validation_rules", "templates")
        }

    for k, v in _DEFAULT.items():
        if k not in data:
            data[k] = v
        else:
            for subk, subv in v.items():
                if subk not in data[k]:
                    data[k][subk] = subv
    return data


def save_structure_templates(templates: dict) -> None:
    """持久化变量结构模板，保留 YAML 中其余节点（statistical_formats 等）不动。"""
    if _TEMPLATE_FILE.exists():
        with open(_TEMPLATE_FILE, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    else:
        raw = {}

    templates_list = [{"type": k, **v} for k, v in templates.items()]
    raw["version"] = 2
    raw["templates"] = templates_list

    with open(_TEMPLATE_FILE, "w", encoding="utf-8") as f:
        yaml.dump(raw, f, allow_unicode=True, sort_keys=False, default_flow_style=False)


def get_var_types(templates: dict) -> list[str]:
    """返回有序变量类型列表：内置基础类型在前，自定义类型追加在后。"""
    custom = [k for k in templates if k not in _BASE_TYPES]
    return _BASE_TYPES + custom


# ── 统计量格式模板（疗效终点用）──────────────────────────────────────────────

def _parse_stat_item(it: dict) -> Optional[StatItem]:
    item_id = it.get("item_id") or it.get("subgroup_id")
    if not item_id:
        return None
    return StatItem(
        item_id=item_id,
        label=it.get("label", ""),
        aval_template=it.get("aval_template", ""),
        aval_options=it.get("aval_options") or [],
        special_values=it.get("special_values") or [],
        unit_hint=it.get("unit_hint"),
        default_checked=it.get("default_checked", True),
        has_children=it.get("has_children", False),
        children_template=it.get("children_template") or [],
    )


def _stat_item_to_dict(item: StatItem) -> dict:
    d: dict = {
        "item_id": item.item_id,
        "label": item.label,
        "aval_template": item.aval_template,
        "aval_options": item.aval_options,
        "default_checked": item.default_checked,
    }
    if item.special_values:
        d["special_values"] = item.special_values
    if item.unit_hint is not None:
        d["unit_hint"] = item.unit_hint
    if item.has_children:
        d["has_children"] = item.has_children
        d["children_template"] = item.children_template
    return d


def load_statistical_formats() -> List[EndpointGroup]:
    """从 YAML 加载统计量格式组，更新 schema.STATISTICAL_FORMAT_GROUPS 和 schema.VALIDATION_RULES。"""
    if not _TEMPLATE_FILE.exists():
        return []
    with open(_TEMPLATE_FILE, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    sf = raw.get("statistical_formats", {})
    groups_data = sf.get("endpoint_groups", []) if isinstance(sf, dict) else []

    groups: List[EndpointGroup] = []
    for g in (groups_data or []):
        subgroups: List[Subgroup] = []
        for sg in g.get("subgroups", []):
            items = [
                it_obj for it in sg.get("items", [])
                if (it_obj := _parse_stat_item(it)) is not None
            ]
            subgroups.append(Subgroup(
                subgroup_id=sg.get("subgroup_id", ""),
                subgroup_name=sg.get("subgroup_name", ""),
                default_expanded=sg.get("default_expanded", True),
                items=items,
            ))
        groups.append(EndpointGroup(
            group_id=g.get("group_id", ""),
            group_name=g.get("group_name", ""),
            icon=g.get("icon", ""),
            description=g.get("description", ""),
            subgroups=subgroups,
        ))

    rules: Dict[str, str] = raw.get("validation_rules") or {}

    _schema.STATISTICAL_FORMAT_GROUPS.clear()
    _schema.STATISTICAL_FORMAT_GROUPS.extend(groups)
    _schema.VALIDATION_RULES.clear()
    _schema.VALIDATION_RULES.update(rules)

    return groups


def save_statistical_formats(
    groups: List[EndpointGroup],
    rules: Dict[str, str],
) -> None:
    """持久化统计量格式组和校验规则，保留 YAML 中 templates 节点不动。"""
    if _TEMPLATE_FILE.exists():
        with open(_TEMPLATE_FILE, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    else:
        raw = {}

    groups_data = []
    for g in groups:
        subgroups_data = []
        for sg in g.subgroups:
            subgroups_data.append({
                "subgroup_id": sg.subgroup_id,
                "subgroup_name": sg.subgroup_name,
                "default_expanded": sg.default_expanded,
                "items": [_stat_item_to_dict(it) for it in sg.items],
            })
        groups_data.append({
            "group_id": g.group_id,
            "group_name": g.group_name,
            "icon": g.icon,
            "description": g.description,
            "subgroups": subgroups_data,
        })

    raw.setdefault("statistical_formats", {})["endpoint_groups"] = groups_data
    raw["validation_rules"] = rules
    raw["version"] = 2

    with open(_TEMPLATE_FILE, "w", encoding="utf-8") as f:
        yaml.dump(raw, f, allow_unicode=True, sort_keys=False, default_flow_style=False)


def get_endpoint_groups() -> List[EndpointGroup]:
    """返回已加载的终点分组列表，未加载时先触发加载。"""
    if not _schema.STATISTICAL_FORMAT_GROUPS:
        load_statistical_formats()
    return _schema.STATISTICAL_FORMAT_GROUPS


def get_group_by_id(group_id: str) -> Optional[EndpointGroup]:
    """按 group_id 查找终点分组。"""
    for g in get_endpoint_groups():
        if g.group_id == group_id:
            return g
    return None


def get_default_checked_items(group_id: str) -> List[StatItem]:
    """返回指定终点类型下所有 default_checked=True 的 StatItem（跨 subgroup 扁平化）。"""
    group = get_group_by_id(group_id)
    if not group:
        return []
    return [it for sg in group.subgroups for it in sg.items if it.default_checked]


def validate_aval_format(aval: str, template: str) -> Tuple[bool, str]:
    """校验 aval 是否符合 template 对应的格式规则，无规则时视为合法。"""
    pattern = _schema.VALIDATION_RULES.get(template)
    if not pattern:
        return True, ""
    if re.match(pattern, aval.strip()):
        return True, ""
    return False, f"格式应为: {template}"


def get_all_stat_items_flat() -> List[Tuple[str, str, StatItem]]:
    """扁平返回所有统计量，格式 (group_id, subgroup_id, StatItem)。"""
    return [
        (g.group_id, sg.subgroup_id, it)
        for g in get_endpoint_groups()
        for sg in g.subgroups
        for it in sg.items
    ]


@st.cache_data(ttl=60)
def load_stat_groups_for_edit() -> List[EndpointGroup]:
    """
    为模板配置 UI 加载统计量格式组。
    @st.cache_data 跨 rerun 返回同一对象引用，UI 对其的修改在同一会话内持久，
    调用 st.cache_data.clear() 后下次返回从文件重新加载的新对象。
    不更新 schema.STATISTICAL_FORMAT_GROUPS 单例，与运行时路径解耦。
    """
    if not _TEMPLATE_FILE.exists():
        return []
    with open(_TEMPLATE_FILE, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    sf = raw.get("statistical_formats", {})
    groups_data = sf.get("endpoint_groups", []) if isinstance(sf, dict) else []
    groups: List[EndpointGroup] = []
    for g in (groups_data or []):
        subgroups: List[Subgroup] = []
        for sg in g.get("subgroups", []):
            items = [
                it_obj for it in sg.get("items", [])
                if (it_obj := _parse_stat_item(it)) is not None
            ]
            subgroups.append(Subgroup(
                subgroup_id=sg.get("subgroup_id", ""),
                subgroup_name=sg.get("subgroup_name", ""),
                default_expanded=sg.get("default_expanded", True),
                items=items,
            ))
        groups.append(EndpointGroup(
            group_id=g.get("group_id", ""),
            group_name=g.get("group_name", ""),
            icon=g.get("icon", ""),
            description=g.get("description", ""),
            subgroups=subgroups,
        ))
    return groups


# 模块初始化时自动加载，确保 STATISTICAL_FORMAT_GROUPS / VALIDATION_RULES 可用
try:
    load_statistical_formats()
except Exception:
    pass
