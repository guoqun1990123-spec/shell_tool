"""YAML 读写，与 R 端 read_yaml_config.R schema 对齐。"""
import math
from pathlib import Path

import pandas as pd
import yaml

from schema import (
    CONFIG_COLS, DATASET_TABLE_COLS, DATASET_LIST_COLS,
    CONFIG_NUM_COLS, DATASET_TABLE_NUM_COLS, DATASET_LIST_NUM_COLS,
)


# ── 内部工具 ───────────────────────────────────────────────────────────────

def _clean_val(v):
    """将 NaN/None → None（YAML 的 null），保持数值类型。"""
    if v is None:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    return v


def _df_to_records(df: pd.DataFrame) -> list[dict]:
    """DataFrame → list[dict]，空值统一为 None。"""
    return [
        {k: _clean_val(v) for k, v in row.items()}
        for row in df.to_dict(orient="records")
    ]


def _records_to_df(records: list[dict], cols: list[str], num_cols: set[str]) -> pd.DataFrame:
    """list[dict] → DataFrame，补齐缺失列，强制数字列类型。"""
    if not records:
        df = pd.DataFrame(columns=cols)
    else:
        df = pd.DataFrame(records)
        # 补齐缺失列
        for c in cols:
            if c not in df.columns:
                df[c] = None
        # 只保留已知列，顺序与定义一致
        df = df[[c for c in cols if c in df.columns]]
    # 数字列转 float（支持 NA）
    for c in num_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    # 其余列填空字符串（None → ""），方便编辑器显示
    for c in df.columns:
        if c not in num_cols:
            df[c] = df[c].fillna("").astype(str)
    return df


# ── 公开 API ───────────────────────────────────────────────────────────────

def load_yaml(path: str | Path) -> tuple[pd.DataFrame, dict[str, pd.DataFrame], dict[str, str]]:
    """
    读取 YAML，返回 (config_df, datasets, figures)。
    datasets 键名 = sheet 名；'list' sheet 使用 DATASET_LIST_COLS，其余用 DATASET_TABLE_COLS。
    figures = {table_no: base64_str}，图形行的嵌入图片；无则返回空 dict。
    """
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    config_records = raw.get("config", []) or []
    config_df = _records_to_df(config_records, CONFIG_COLS, CONFIG_NUM_COLS)

    datasets_raw = raw.get("datasets", {}) or {}
    datasets: dict[str, pd.DataFrame] = {}
    for sheet, rows in datasets_raw.items():
        rows = rows or []
        if sheet == "list":
            datasets[sheet] = _records_to_df(rows, DATASET_LIST_COLS, DATASET_LIST_NUM_COLS)
        else:
            datasets[sheet] = _records_to_df(rows, DATASET_TABLE_COLS, DATASET_TABLE_NUM_COLS)

    figures: dict[str, str] = raw.get("figures", {}) or {}

    return config_df, datasets, figures


def dump_yaml(
    config_df: pd.DataFrame,
    datasets: dict[str, pd.DataFrame],
    protocol_name: str = "",
    figures: dict[str, str] | None = None,
) -> str:
    """
    序列化为 YAML 字符串。
    - 键顺序稳定（sort_keys=False），减少 Git diff 噪声。
    - 含空格的列名（Section no / table no）自动被 pyyaml 加引号；Source_Data 无需引号。
    - 空字符串字段写成 ""，None 写成 null，与 R 端 is.na 兼容。
    - figures: {table_no: base64_str}，非空时写入顶层 figures 块。
    """
    config_records = _df_to_records(config_df)

    datasets_out: dict[str, list[dict]] = {}
    for sheet, df in datasets.items():
        datasets_out[sheet] = _df_to_records(df)

    doc: dict = {
        "version": 1,
        "config": config_records,
        "datasets": datasets_out,
    }

    # 仅在有嵌入图片时写入 figures 块，避免空块污染 YAML
    if figures:
        doc["figures"] = figures

    # yaml.dump 默认对含空格的键加引号，allow_unicode 保留中文
    return yaml.dump(
        doc,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
        indent=2,
    )


def list_yaml_files(config_dir: str | Path) -> list[Path]:
    """扫描目录下所有 config_*.yaml 文件，按修改时间倒序返回。"""
    d = Path(config_dir)
    if not d.exists():
        return []
    files = sorted(d.glob("config_*.yaml"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files
