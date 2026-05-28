"""变量类型模板的加载/保存，读写 web/variable_templates.yaml。"""
from pathlib import Path
import yaml
import streamlit as st

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


@st.cache_data(ttl=60)
def load_templates() -> dict:
    """加载模板，文件不存在时返回内置默认值。"""
    if not _TEMPLATE_FILE.exists():
        return _DEFAULT
    with open(_TEMPLATE_FILE, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    for k, v in _DEFAULT.items():
        if k not in data:
            data[k] = v
        else:
            # 补全缺失的子键（如旧文件缺少 aval_options）
            for subk, subv in v.items():
                if subk not in data[k]:
                    data[k][subk] = subv
    return data


def save_templates(templates: dict) -> None:
    """持久化模板到 YAML 文件。"""
    with open(_TEMPLATE_FILE, "w", encoding="utf-8") as f:
        yaml.dump(templates, f, allow_unicode=True, sort_keys=False, default_flow_style=False)


def get_var_types(templates: dict) -> list[str]:
    """
    返回有序变量类型列表：内置基础类型在前，自定义类型（非内置）追加在后。
    """
    custom = [k for k in templates if k not in _BASE_TYPES]
    return _BASE_TYPES + custom
