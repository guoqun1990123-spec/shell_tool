"""R 渲染器：保存临时 YAML、调用 Rscript、返回结果。"""
from __future__ import annotations

import subprocess
import time
from pathlib import Path

# 项目根目录（web/ 的上一级）
_REPO_ROOT = Path(__file__).parent.parent
_TEMP_YAML = _REPO_ROOT / "config" / "temp_render.yaml"
_TEMP_DOCX = _REPO_ROOT / "output" / "temp_output.docx"
_RENDER_CLI = _REPO_ROOT / "R" / "render_cli.R"


def _ensure_output_dir() -> None:
    _TEMP_DOCX.parent.mkdir(parents=True, exist_ok=True)
    _TEMP_YAML.parent.mkdir(parents=True, exist_ok=True)


def run_render(yaml_content: str) -> dict:
    """
    Write yaml_content to temp file, invoke Rscript, return result dict:
      {
        'status': 'success' | 'error',
        'output_path': Path | None,
        'output_bytes': bytes | None,
        'elapsed': float,
        'stdout': str,
        'stderr': str,
        'error_summary': str | None,   # first meaningful R error line
        'seq_hint': int | None,        # SeqNum extracted from error, if any
      }
    """
    _ensure_output_dir()

    # 写临时 YAML
    _TEMP_YAML.write_text(yaml_content, encoding="utf-8")

    t0 = time.time()
    try:
        result = subprocess.run(
            [
                "Rscript",
                str(_RENDER_CLI),
                "--config", str(_TEMP_YAML),
                "--output", str(_TEMP_DOCX),
            ],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=str(_REPO_ROOT),
        )
    except subprocess.TimeoutExpired:
        elapsed = time.time() - t0
        return {
            "status": "error",
            "output_path": None,
            "output_bytes": None,
            "elapsed": elapsed,
            "stdout": "",
            "stderr": "",
            "error_summary": "渲染超时（超过 300 秒）",
            "seq_hint": None,
        }
    except FileNotFoundError:
        elapsed = time.time() - t0
        return {
            "status": "error",
            "output_path": None,
            "output_bytes": None,
            "elapsed": elapsed,
            "stdout": "",
            "stderr": "未找到 Rscript，请确认 R 已安装并在 PATH 中",
            "error_summary": "未找到 Rscript",
            "seq_hint": None,
        }

    elapsed = time.time() - t0

    if result.returncode != 0 or not _TEMP_DOCX.exists():
        summary, seq_hint = _parse_r_error(result.stderr or result.stdout)
        return {
            "status": "error",
            "output_path": None,
            "output_bytes": None,
            "elapsed": elapsed,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "error_summary": summary,
            "seq_hint": seq_hint,
        }

    output_bytes = _TEMP_DOCX.read_bytes()
    return {
        "status": "success",
        "output_path": _TEMP_DOCX,
        "output_bytes": output_bytes,
        "elapsed": elapsed,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "error_summary": None,
        "seq_hint": None,
    }


def _parse_r_error(log: str) -> tuple[str, int | None]:
    """Extract first Error/stop line and any SeqNum hint."""
    seq_hint: int | None = None
    summary_line = ""

    for line in log.splitlines():
        stripped = line.strip()
        if not summary_line and (
            stripped.startswith("Error") or "Error in" in stripped or "stop(" in stripped
        ):
            summary_line = stripped[:200]
        # Look for "Seq X" or "SeqNum X" pattern
        if seq_hint is None:
            import re
            m = re.search(r"[Ss]eq(?:[Nn]um)?\s*[=:]?\s*(\d+)", stripped)
            if m:
                seq_hint = int(m.group(1))

    if not summary_line:
        # Fall back to last non-empty line
        lines = [l.strip() for l in log.splitlines() if l.strip()]
        summary_line = lines[-1][:200] if lines else "未知错误"

    return summary_line, seq_hint


def run_preview(card: dict, datasets: dict, protocol_name: str = "preview") -> dict:
    """
    将单个卡片渲染为单条目YAML，复用 run_render() 生成单表Word文档。
    card: config_editor card dict（含 _* 元数据字段，会被过滤掉）
    datasets: 完整 datasets dict（只用到 card["Datasets"] 对应的 sheet）
    """
    import pandas as pd
    import sys
    import os
    sys.path.insert(0, str(Path(__file__).parent))
    from yaml_io import dump_yaml
    from schema import CONFIG_COLS

    row = {k: v for k, v in card.items() if not k.startswith("_")}
    row["SeqNum"] = 1
    for col in CONFIG_COLS:
        if col not in row:
            row[col] = ""
    config_df = pd.DataFrame([row], columns=CONFIG_COLS)

    ds_name = str(card.get("Datasets") or "").strip()
    macvar = str(card.get("MacVar") or "").strip()
    preview_datasets: dict = {}
    if ds_name and ds_name in datasets:
        preview_datasets[ds_name] = datasets[ds_name]
    if macvar == "RptList" and "list" in datasets:
        preview_datasets["list"] = datasets["list"]

    yaml_content = dump_yaml(config_df, preview_datasets, protocol_name)
    return run_render(yaml_content)
