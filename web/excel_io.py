"""Excel 读取，与 yaml_io.load_yaml() 返回相同结构。"""
from pathlib import Path

import pandas as pd

from schema import (
    CONFIG_COLS, CONFIG_NUM_COLS,
    DATASET_TABLE_COLS, DATASET_TABLE_NUM_COLS,
    DATASET_LIST_COLS, DATASET_LIST_NUM_COLS,
)
from yaml_io import _records_to_df

# 镜像 R/utils/read_config.R 的旧列名兼容映射（config 表）
_COL_ALIASES = {
    "Subgrop":     "Subgrp",
    "PgmNote":     "PgmNotes",
    "Source data": "Source_Data",
    "Source_data": "Source_Data",
    "Source Data": "Source_Data",
    "Datesets":    "Datasets",
    "RfeTFL":      "RefTFL",
}

# datasets 表的中文列名别名（immu 等 sheet 使用中文）
_DATASET_COL_ALIASES = {
    "药物": "Drug",
    "访视": "Visit",
    "基线": "Base",
}


def _apply_column_aliases(df: pd.DataFrame) -> pd.DataFrame:
    """将旧列名替换为新列名，仅在目标列不存在时执行。"""
    rename = {}
    for old, new in _COL_ALIASES.items():
        if old in df.columns and new not in df.columns:
            rename[old] = new
    if rename:
        df = df.rename(columns=rename)
    return df


def _apply_dataset_aliases(df: pd.DataFrame) -> pd.DataFrame:
    """将 datasets 表中文列名映射为英文 canonical 列名。"""
    rename = {old: new for old, new in _DATASET_COL_ALIASES.items()
              if old in df.columns and new not in df.columns}
    return df.rename(columns=rename) if rename else df


def list_excel_pairs(config_dir: str | Path) -> tuple[list[Path], list[Path]]:
    """
    扫描目录下 config_*.xlsx 与 datasets_*.xlsx，按修改时间倒序分别返回。
    """
    d = Path(config_dir)
    if not d.exists():
        return [], []
    cfg_files = sorted(d.glob("config_*.xlsx"), key=lambda p: p.stat().st_mtime, reverse=True)
    ds_files = sorted(d.glob("datasets_*.xlsx"), key=lambda p: p.stat().st_mtime, reverse=True)
    return cfg_files, ds_files


def load_excel(
    config_path: str | Path,
    datasets_path: str | Path,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    """
    读取 Excel 配对文件，返回与 load_yaml() 完全一致的 (config_df, datasets)。
    """
    # ── config ───────────────────────────────────────────────────────────────
    raw_cfg = pd.read_excel(config_path, sheet_name=0, dtype=str)
    raw_cfg = _apply_column_aliases(raw_cfg)
    config_df = _records_to_df(
        raw_cfg.to_dict(orient="records"),
        CONFIG_COLS,
        CONFIG_NUM_COLS,
    )

    # ── datasets ─────────────────────────────────────────────────────────────
    sheets: dict[str, pd.DataFrame] = pd.read_excel(
        datasets_path, sheet_name=None, dtype=str
    )
    datasets: dict[str, pd.DataFrame] = {}
    for sheet_name, df in sheets.items():
        df = _apply_dataset_aliases(df)
        if sheet_name == "list":
            datasets[sheet_name] = _records_to_df(
                df.to_dict(orient="records"),
                DATASET_LIST_COLS,
                DATASET_LIST_NUM_COLS,
            )
        else:
            datasets[sheet_name] = _records_to_df(
                df.to_dict(orient="records"),
                DATASET_TABLE_COLS,
                DATASET_TABLE_NUM_COLS,
            )

    return config_df, datasets
