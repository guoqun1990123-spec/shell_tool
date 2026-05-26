"""
校验规则，镜像 R 端 read_yaml_config.R 中 .validate_yaml_input()。
修改此处时同步更新 R 端校验逻辑。
"""
from dataclasses import dataclass

import pandas as pd

from schema import VALID_MACVAR, REQUIRED_COLS


@dataclass
class ValidationError:
    row_idx: int  # 0-based，-1 表示全局错误
    message: str

    def __str__(self):
        if self.row_idx >= 0:
            return f"第 {self.row_idx + 1} 行：{self.message}"
        return self.message


def validate(
    config_df: pd.DataFrame,
    datasets: dict,
) -> list[ValidationError]:
    errors: list[ValidationError] = []
    dataset_keys = set(datasets.keys())
    valid_macvar_lower = {v.lower() for v in VALID_MACVAR}

    # 收集所有 table no，供 mtext RefTFL 校验用
    table_nos = set()
    if "table no" in config_df.columns:
        table_nos = set(config_df["table no"].dropna().astype(str).str.strip())

    for i, row in config_df.iterrows():
        idx = config_df.index.get_loc(i)

        # 必填列
        for col in REQUIRED_COLS:
            val = row.get(col, "")
            if pd.isna(val) or str(val).strip() == "":
                errors.append(ValidationError(idx, f"必填列 '{col}' 为空"))

        macvar = str(row.get("MacVar", "") or "").strip()
        if macvar.lower() not in valid_macvar_lower:
            errors.append(ValidationError(
                idx,
                f"MacVar='{macvar}' 不合法（允许：{', '.join(v or '空' for v in VALID_MACVAR)}）"
            ))
            continue  # 后续校验依赖合法的 MacVar，跳过

        datasets_val = str(row.get("Datasets", "") or "").strip()

        # Datasets 引用校验（非 mtext 且 Datasets 非空）
        if macvar.lower() != "mtext" and datasets_val:
            if datasets_val not in dataset_keys:
                errors.append(ValidationError(
                    idx,
                    f"Datasets='{datasets_val}' 在 datasets 中未定义（现有：{', '.join(sorted(dataset_keys)) or '无'}）"
                ))

        # RptList 必须有 list 表
        if macvar.lower() == "rptlist" and "list" not in dataset_keys:
            errors.append(ValidationError(idx, "MacVar='RptList' 但 datasets 中缺少 'list' 表"))

        # mtext 的 RefTFL 必须指向存在的 table no
        if macvar.lower() == "mtext":
            ref = str(row.get("RefTFL", "") or "").strip()
            if not ref:
                errors.append(ValidationError(idx, "MacVar='mtext' 时 RefTFL 不能为空"))
            elif ref not in table_nos:
                errors.append(ValidationError(
                    idx, f"RefTFL='{ref}' 找不到对应的 table no"
                ))

    return errors
