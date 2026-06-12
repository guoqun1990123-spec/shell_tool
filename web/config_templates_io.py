"""Config 模板 IO：section_map + pop_options 的加载与保存。"""
from __future__ import annotations

from pathlib import Path

import streamlit as st
import yaml

TEMPLATES_PATH = Path(__file__).parent / "config_templates.yaml"

_DEFAULTS: dict = {
    "section_map": {},
    "pop_options": [],
    "footnote_snippets": [],
    "trtlab_presets": [],
}


@st.cache_data(ttl=60)
def load_config_templates() -> dict:
    if not TEMPLATES_PATH.exists():
        return dict(_DEFAULTS)
    with open(TEMPLATES_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return {
        "section_map": dict(data.get("section_map", {})),
        "pop_options": list(data.get("pop_options", [])),
        "footnote_snippets": list(data.get("footnote_snippets", [])),
        "trtlab_presets": list(data.get("trtlab_presets", [])),
    }


def save_config_templates(templates: dict) -> None:
    with open(TEMPLATES_PATH, "w", encoding="utf-8") as f:
        yaml.dump(templates, f, allow_unicode=True, default_flow_style=False)
