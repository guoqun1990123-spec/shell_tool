# web/utils.py
"""共享工具函数（无 Streamlit 依赖）。"""
from __future__ import annotations
import re


def sec_sort_key(sec_no: str) -> tuple:
    """将 '14.1.2' 拆成 (14, 1, 2) 用于数值排序。"""
    parts = re.split(r"[.\-]", sec_no.strip())
    result = []
    for p in parts:
        try:
            result.append(int(p))
        except ValueError:
            result.append(p)
    return tuple(result)
