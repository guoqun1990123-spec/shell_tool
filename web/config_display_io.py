"""Config 字段显示级别配置的 IO。"""
from __future__ import annotations

from pathlib import Path

import streamlit as st
import yaml

LEVELS_PATH = Path(__file__).parent / "config_display_levels.yaml"

# 6 个必显示字段，代码硬锁定，不受 YAML 影响
REQUIRED_FIELDS: list[str] = [
    "SeqNum", "Section no", "Section title", "cat", "table no", "title"
]

_DEFAULTS: dict = {
    "default_collapse": True,
    "field_levels": {
        "SeqNum": "required",
        "Section no": "required",
        "Section title": "required",
        "cat": "required",
        "table no": "required",
        "title": "required",
        "pop": "level1",
        "footnote1": "level1",
        "footnote2": "level1",
        "footnote3": "level1",
        "footnote4": "level1",
        "footnote5": "level1",
        "footnote6": "level1",
        "footnote7": "level1",
        "Datasets": "level1",
        "MacVar": "level1",
        "Trtlab": "level1",
        "Dutoffdate": "level2",
        "Source_Data": "level2",
        "PgmNotes": "level2",
        "Subgrp": "level2",
        "Adcols": "level2",
        "Varlab": "level2",
        "Labparm": "level2",
        "ByseqL": "level2",
        "RefTFL": "level2",
    },
}


@st.cache_data(ttl=60)
def load_display_levels() -> dict:
    if not LEVELS_PATH.exists():
        return dict(_DEFAULTS)
    with open(LEVELS_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    levels = dict(_DEFAULTS["field_levels"])
    levels.update(data.get("field_levels", {}))
    # Enforce required fields regardless of YAML content
    for f in REQUIRED_FIELDS:
        levels[f] = "required"
    return {
        "default_collapse": bool(data.get("default_collapse", True)),
        "field_levels": levels,
    }


def save_display_levels(cfg: dict) -> None:
    levels = dict(cfg.get("field_levels", {}))
    for f in REQUIRED_FIELDS:
        levels[f] = "required"
    out = {
        "default_collapse": bool(cfg.get("default_collapse", True)),
        "field_levels": levels,
    }
    with open(LEVELS_PATH, "w", encoding="utf-8") as f:
        yaml.dump(out, f, allow_unicode=True, default_flow_style=False)


def field_level(field: str, display_cfg: dict) -> str:
    """Return level string for a field: required / level1 / level2 / hidden."""
    if field in REQUIRED_FIELDS:
        return "required"
    return display_cfg.get("field_levels", {}).get(field, "level2")
