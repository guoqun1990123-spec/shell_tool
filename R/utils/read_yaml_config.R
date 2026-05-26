# YAML配置读取模块

# 合法的MacVar取值（大小写不敏感）
.VALID_MACVAR <- c("", "pstab", "rptlist", "mtext", "kmplot", "swimplot",
                   "waterfallplot", "spiderplot", "seriesplot", "forestplot")

# 应用列名兼容映射（与read_config.R保持一致）
.apply_column_aliases <- function(df) {
  col_map <- c(
    "Subgrop"     = "Subgrp",
    "PgmNote"     = "PgmNotes",
    "Source data" = "Source_Data",
    "Source_data" = "Source_Data",
    "Source Data" = "Source_Data",
    "Datesets"    = "Datasets",
    "RfeTFL"      = "RefTFL"
  )
  for (old in names(col_map)) {
    new <- col_map[[old]]
    if (old %in% colnames(df) && !new %in% colnames(df)) {
      colnames(df)[colnames(df) == old] <- new
    }
  }
  df
}

# 内部校验：发现问题时stop()，信息含行号
.validate_yaml_input <- function(raw) {
  if (!is.list(raw)) stop("YAML根节点必须是映射对象")
  if (is.null(raw$config)) stop("YAML缺少顶层字段 'config'")
  if (!is.list(raw$config)) stop("'config' 字段必须是对象数组")
  if (is.null(raw$datasets)) stop("YAML缺少顶层字段 'datasets'")
  if (!is.list(raw$datasets)) stop("'datasets' 字段必须是映射对象")

  dataset_keys <- names(raw$datasets)

  for (i in seq_along(raw$config)) {
    row <- raw$config[[i]]
    prefix <- sprintf("config[%d]", i)

    # 必填列
    for (col in c("SeqNum", "Section no", "MacVar")) {
      val <- row[[col]]
      if (is.null(val) || (length(val) == 1 && is.na(val))) {
        stop(sprintf("%s: 必填列 '%s' 缺失或为空", prefix, col))
      }
    }

    macvar <- if (is.null(row$MacVar) || is.na(row$MacVar)) "" else row$MacVar
    if (!tolower(macvar) %in% .VALID_MACVAR) {
      stop(sprintf(
        "%s: MacVar='%s' 不是合法取值（允许: %s）",
        prefix, macvar,
        paste(c("", "PStab", "RptList", "mtext", "KMplot", "Swimplot",
                "WaterfallPlot", "Spiderplot", "Seriesplot", "Forestplot"),
              collapse = ", ")
      ))
    }

    ds <- if (is.null(row$Datasets) || is.na(row$Datasets)) "" else row$Datasets
    if (tolower(macvar) != "mtext" && nchar(ds) > 0) {
      if (!ds %in% dataset_keys) {
        stop(sprintf(
          "%s: Datasets='%s' 在 datasets 中找不到对应的表（现有: %s）",
          prefix, ds, paste(dataset_keys, collapse = ", ")
        ))
      }
    }

    if (tolower(macvar) == "rptlist" && !"list" %in% dataset_keys) {
      stop(sprintf(
        "%s: MacVar='RptList' 但 datasets 中缺少 'list' 表",
        prefix
      ))
    }
  }
}

#' 读取YAML配置文件，返回与read_config()+read_datasets()等价的结构
#'
#' @param yaml_file YAML文件路径
#' @return list(config = data.frame, datasets = named list of data.frame)
read_yaml_input <- function(yaml_file) {
  if (!requireNamespace("yaml", quietly = TRUE)) {
    stop("请先安装yaml包：install.packages('yaml')")
  }

  raw <- yaml::read_yaml(yaml_file, fileEncoding = "UTF-8")

  .validate_yaml_input(raw)

  # --- 构建 config data.frame ---
  # bind_rows自动对齐列名，缺失补NA
  config <- dplyr::bind_rows(lapply(raw$config, function(row) {
    as.data.frame(lapply(row, function(v) if (is.null(v)) NA else v),
                  stringsAsFactors = FALSE, check.names = FALSE)
  }))

  # 应用列名兼容映射
  config <- .apply_column_aliases(config)

  # 补充ByseqL列（与read_config.R保持一致）
  if (!"ByseqL" %in% colnames(config)) {
    config$ByseqL <- NA
  }

  # 丢弃未知列并发警告
  known_cols <- c(
    "SeqNum", "Section no", "Section title", "cat", "table no", "title",
    "pop", "MacVar", "Datasets", "Trtlab", "Subgrp", "Adcols", "Varlab",
    "Labparm", "footnote1", "footnote2", "footnote3", "footnote4",
    "footnote5", "footnote6", "footnote7", "PgmNotes", "ByseqL",
    "RefTFL", "Dutoffdate", "Source_Data"
  )
  unknown <- setdiff(colnames(config), known_cols)
  if (length(unknown) > 0) {
    warning(sprintf("YAML config 包含未知列，已忽略: %s", paste(unknown, collapse = ", ")))
    config <- config[, intersect(colnames(config), known_cols), drop = FALSE]
  }

  # --- 构建 datasets named list ---
  datasets <- lapply(raw$datasets, function(sheet_rows) {
    dplyr::bind_rows(lapply(sheet_rows, function(row) {
      as.data.frame(lapply(row, function(v) if (is.null(v)) NA else v),
                    stringsAsFactors = FALSE, check.names = FALSE)
    }))
  })

  list(config = config, datasets = datasets)
}
