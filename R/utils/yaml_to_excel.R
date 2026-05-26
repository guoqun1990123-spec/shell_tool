# yaml_to_excel.R
# 将单文件 YAML 配置转换为 config.xlsx + datasets.xlsx
#
# 用法：
#   source("R/utils/yaml_to_excel.R")
#   yaml_to_excel("config/config_ISS_20260515_113046.yaml")
#   # 默认输出到与 YAML 同目录，文件名去掉时间戳后缀

yaml_to_excel <- function(yaml_file,
                           config_out   = NULL,
                           datasets_out = NULL) {
  if (!requireNamespace("yaml",      quietly = TRUE)) stop("需要 yaml 包")
  if (!requireNamespace("openxlsx",  quietly = TRUE)) stop("需要 openxlsx 包")

  # ── 默认输出路径 ──────────────────────────────────────────────────────────────
  base_dir  <- dirname(yaml_file)
  stem      <- sub("_\\d{8}_\\d{6}$", "",
                   tools::file_path_sans_ext(basename(yaml_file)))
  if (is.null(config_out))
    config_out   <- file.path(base_dir, paste0(stem, "_config.xlsx"))
  if (is.null(datasets_out))
    datasets_out <- file.path(base_dir, paste0(stem, "_datasets.xlsx"))

  # ── 读取 YAML ─────────────────────────────────────────────────────────────────
  raw <- yaml::read_yaml(yaml_file)

  # ── config → data.frame ───────────────────────────────────────────────────────
  config_cols <- c(
    "SeqNum", "Section no", "Section title", "cat", "table no", "title",
    "pop", "MacVar", "Datasets", "Trtlab", "Subgrp", "Adcols", "Varlab",
    "Labparm", "footnote1", "footnote2", "footnote3", "footnote4",
    "footnote5", "footnote6", "footnote7", "PgmNotes", "ByseqL",
    "RefTFL", "Dutoffdate", "Source_Data"
  )

  config_df <- do.call(rbind, lapply(raw$config, function(row) {
    vals <- lapply(config_cols, function(col) {
      v <- row[[col]]
      if (is.null(v)) NA_character_ else as.character(v)
    })
    names(vals) <- config_cols
    as.data.frame(vals, stringsAsFactors = FALSE, check.names = FALSE)
  }))

  # ── datasets → list of data.frames ───────────────────────────────────────────
  datasets_list <- lapply(raw$datasets, function(sheet_rows) {
    if (length(sheet_rows) == 0L) return(data.frame())

    # 收集所有出现过的列名（保持首次出现顺序）
    all_cols <- unique(unlist(lapply(sheet_rows, names)))

    do.call(rbind, lapply(sheet_rows, function(row) {
      vals <- lapply(all_cols, function(col) {
        v <- row[[col]]
        if (is.null(v)) NA else v
      })
      names(vals) <- all_cols
      as.data.frame(vals, stringsAsFactors = FALSE, check.names = FALSE)
    }))
  })

  # ── 写 config.xlsx ────────────────────────────────────────────────────────────
  wb_cfg <- openxlsx::createWorkbook()
  openxlsx::addWorksheet(wb_cfg, "config")

  # 文字环绕样式（处理含换行的 Trtlab 等字段）
  wrap_style <- openxlsx::createStyle(wrapText = TRUE, valign = "top")

  openxlsx::writeData(wb_cfg, "config", config_df, rowNames = FALSE)
  openxlsx::addStyle(wb_cfg, "config", wrap_style,
                     rows = seq_len(nrow(config_df) + 1L),
                     cols = seq_len(ncol(config_df)),
                     gridExpand = TRUE)
  openxlsx::setColWidths(wb_cfg, "config", cols = seq_len(ncol(config_df)),
                         widths = "auto")
  openxlsx::saveWorkbook(wb_cfg, config_out, overwrite = TRUE)
  message("config.xlsx 写入: ", config_out)

  # ── 写 datasets.xlsx ──────────────────────────────────────────────────────────
  wb_ds <- openxlsx::createWorkbook()

  for (sheet_name in names(datasets_list)) {
    df <- datasets_list[[sheet_name]]
    # Excel sheet 名最长 31 字符
    safe_name <- substr(sheet_name, 1L, 31L)
    openxlsx::addWorksheet(wb_ds, safe_name)
    if (nrow(df) > 0L && ncol(df) > 0L) {
      openxlsx::writeData(wb_ds, safe_name, df, rowNames = FALSE)
      openxlsx::addStyle(wb_ds, safe_name, wrap_style,
                         rows = seq_len(nrow(df) + 1L),
                         cols = seq_len(ncol(df)),
                         gridExpand = TRUE)
      openxlsx::setColWidths(wb_ds, safe_name,
                             cols = seq_len(ncol(df)), widths = "auto")
    }
  }

  openxlsx::saveWorkbook(wb_ds, datasets_out, overwrite = TRUE)
  message("datasets.xlsx 写入: ", datasets_out)

  invisible(list(config = config_df, datasets = datasets_list))
}
