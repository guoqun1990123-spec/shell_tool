# 配置读取模块

#' 读取config.xlsx，并统一列名到最新规范
read_config <- function(config_file) {
  config <- read.xlsx(config_file, sheet = 1)

  # R的openxlsx会把空格转为点号，需要还原
  colnames(config) <- gsub("\\.", " ", colnames(config))

  # 列名兼容映射（旧名 -> 新名）
  col_map <- c(
    "Subgrop"    = "Subgrp",
    "PgmNote"    = "PgmNotes",
    "Source data" = "Source_Data",
    "Source_data" = "Source_Data",
    "Source Data" = "Source_Data",
    "Datesets"   = "Datasets",
    "RfeTFL"     = "RefTFL"
  )
  for (old in names(col_map)) {
    new <- col_map[[old]]
    if (old %in% colnames(config) && !new %in% colnames(config)) {
      colnames(config)[colnames(config) == old] <- new
    }
  }

  # 若缺少ByseqL列则补充空列
  if (!"ByseqL" %in% colnames(config)) {
    config$ByseqL <- NA
  }

  return(config)
}

#' 读取datasets.xlsx所有工作表
read_datasets <- function(datasets_file) {
  sheets <- getSheetNames(datasets_file)
  datasets <- list()
  for (sheet in sheets) {
    datasets[[sheet]] <- read.xlsx(datasets_file, sheet = sheet)
  }
  return(datasets)
}
