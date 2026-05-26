# 文档组装模块

# 安全判断：值是否为空（处理NULL/NA/空字符串）
is_empty <- function(x) {
  is.null(x) || length(x) == 0 || all(is.na(x)) || all(x == "")
}

#' 添加支持富文本标记的段落到 Word 文档
#' 含标记（^[]/_{[}]）时用 body_add_fpar，否则用 body_add_par
body_add_rich_par <- function(doc, text, style = "Normal",
                               font_family = "宋体", font_size = 10.5,
                               color = "black") {
  if (is_empty(text)) return(doc)
  if (has_rich_text(text)) {
    base_prop <- fp_text(
      font.size   = font_size,
      font.family = font_family,
      color       = color
    )
    doc <- body_add_fpar(doc, parse_rich_text_to_fpar(text, base_prop),
                         style = style)
  } else {
    doc <- body_add_par(doc, text, style = style)
  }
  return(doc)
}

#' 添加表格到Word文档
add_table_to_doc <- function(doc, config_row, datasets, displayed_sections = c()) {

  # 获取数据集
  dataset_name <- config_row$Datasets
  if (is.null(datasets[[dataset_name]])) {
    cat(sprintf("  警告：未找到数据集 %s\n", dataset_name))
    return(doc)
  }

  dataset <- datasets[[dataset_name]]

  # 过滤exclude=1的行
  if ("exclude" %in% colnames(dataset)) {
    dataset <- dataset[is.na(dataset$exclude) | dataset$exclude != 1, ]
  }

  # 构建表头
  varlab <- ifelse(is.na(config_row$Varlab), "指标", config_row$Varlab)
  header <- build_table_header(
    trtlab = config_row$Trtlab,
    subgrop = config_row$Subgrp,
    varlab = varlab,
    adcols = config_row$Adcols
  )

  # 构建表格数据
  table_data <- build_table_data(dataset, header, varlab)

  # 创建flextable
  ft <- create_flextable(table_data, header, varlab)

  # 添加章节标题（仅当该章节首次出现时）
  section_no <- config_row$`Section no`
  if (!is_empty(section_no) && !is_empty(config_row$`Section title`)) {
    if (!section_no %in% displayed_sections) {
      section_text <- paste0(section_no, " ", config_row$`Section title`)
      doc <- body_add_par(doc, section_text, style = "heading 1")
    }
  }

  # 添加表标题（cat + table no + title - pop）
  table_title <- ""
  if (!is_empty(config_row$cat)) {
    table_title <- paste0(config_row$cat, config_row$`table no`)
  } else {
    table_title <- config_row$`table no`
  }
  if (!is_empty(config_row$title)) {
    table_title <- paste0(table_title, " ", config_row$title)
  }
  if (!is_empty(config_row$pop)) {
    table_title <- paste0(table_title, " - ", config_row$pop)
  }
  doc <- body_add_par(doc, table_title, style = "heading 2")

  # 添加Labparm（表上方内容）
  if (!is_empty(config_row$Labparm)) {
    doc <- body_add_rich_par(doc, config_row$Labparm, style = "Normal")
  }

  # 添加表格
  doc <- body_add_flextable(doc, ft)

  # 添加脚注
  footnotes <- c()
  for (i in 1:7) {
    fn_col <- paste0("footnote", i)
    if (fn_col %in% colnames(config_row) && !is.na(config_row[[fn_col]])) {
      footnotes <- c(footnotes, config_row[[fn_col]])
    }
  }

  if (length(footnotes) > 0) {
    fn_text <- paste("注：", paste(footnotes, collapse = " "))
    doc <- body_add_rich_par(doc, fn_text, style = "Normal")
  }

  # 添加编程说明（蓝色字体）
  if (!is_empty(config_row$PgmNotes)) {
    pgm_text <- paste("编程说明：", config_row$PgmNotes)
    doc <- body_add_rich_par(doc, pgm_text, style = "Normal",
                              font_family = "宋体", font_size = 10.5, color = "blue")
  }

  return(doc)
}

#' 添加清单到Word文档
add_listing_to_doc <- function(doc, config_row, datasets, displayed_sections = c()) {

  # 获取list数据集
  if (is.null(datasets[["list"]])) {
    cat("  警告：未找到list工作表\n")
    return(doc)
  }

  list_data <- datasets[["list"]]

  # 解析ByseqL参数（支持数字或"key = value"格式）
  byseq_str <- config_row$ByseqL
  if (is_empty(byseq_str)) {
    cat("  警告：ByseqL参数为空\n")
    return(doc)
  }

  # 提取Byseq值
  if (is.numeric(byseq_str)) {
    byseq <- byseq_str
  } else {
    # 格式如"bases = 3"，提取等号后的数字
    byseq <- as.numeric(gsub(".*=\\s*", "", byseq_str))
  }

  # 提取清单数据
  listing <- extract_listing_data(list_data, byseq)

  # 构建清单表格
  listing_table <- build_listing_table(listing)

  # 创建flextable
  ft <- create_listing_flextable(listing_table)

  # 添加章节标题（仅当该章节首次出现时）
  section_no <- config_row$`Section no`
  if (!is_empty(section_no) && !is_empty(config_row$`Section title`)) {
    if (!section_no %in% displayed_sections) {
      section_text <- paste0(section_no, " ", config_row$`Section title`)
      doc <- body_add_par(doc, section_text, style = "heading 1")
    }
  }

  # 添加清单标题（cat + table no + title - pop）
  listing_title <- ""
  if (!is_empty(config_row$cat)) {
    listing_title <- paste0(config_row$cat, config_row$`table no`)
  } else {
    listing_title <- config_row$`table no`
  }
  if (!is_empty(config_row$title)) {
    listing_title <- paste0(listing_title, " ", config_row$title)
  }
  if (!is_empty(config_row$pop)) {
    listing_title <- paste0(listing_title, " - ", config_row$pop)
  }
  doc <- body_add_par(doc, listing_title, style = "heading 2")

  # 添加表格
  doc <- body_add_flextable(doc, ft)

  # 添加脚注
  footnotes <- c()
  for (i in 1:7) {
    fn_col <- paste0("footnote", i)
    if (fn_col %in% colnames(config_row) && !is.na(config_row[[fn_col]])) {
      footnotes <- c(footnotes, config_row[[fn_col]])
    }
  }

  if (length(footnotes) > 0) {
    fn_text <- paste("注：", paste(footnotes, collapse = " "))
    doc <- body_add_rich_par(doc, fn_text, style = "Normal")
  }

  # 添加编程说明（蓝色字体）
  if (!is_empty(config_row$PgmNotes)) {
    pgm_text <- paste("编程说明：", config_row$PgmNotes)
    doc <- body_add_rich_par(doc, pgm_text, style = "Normal",
                              font_family = "宋体", font_size = 10.5, color = "blue")
  }

  return(doc)
}

#' 添加mtext（引用已有表格）到Word文档
add_mtext_to_doc <- function(doc, config_row, config, datasets, displayed_sections = c()) {

  # 获取引用的表格编号
  ref_tfl <- config_row$RefTFL
  if (is_empty(ref_tfl)) {
    cat("  警告：mtext的RefTFL为空\n")
    return(doc)
  }

  # 在config中查找引用的表格
  ref_row <- config[config$`table no` == ref_tfl & !is.na(config$`table no`), ]
  if (nrow(ref_row) == 0) {
    cat(sprintf("  警告：未找到引用的表格 %s\n", ref_tfl))
    return(doc)
  }
  ref_row <- ref_row[1, ]

  # 添加章节标题（仅当该章节首次出现时）
  section_no <- config_row$`Section no`
  if (!is_empty(section_no) && !is_empty(config_row$`Section title`)) {
    if (!section_no %in% displayed_sections) {
      section_text <- paste0(section_no, " ", config_row$`Section title`)
      doc <- body_add_par(doc, section_text, style = "heading 1")
    }
  }

  # 添加表标题（cat + table no + title - pop）
  table_title <- ""
  if (!is_empty(config_row$cat)) {
    table_title <- paste0(config_row$cat, config_row$`table no`)
  } else {
    table_title <- config_row$`table no`
  }
  if (!is_empty(config_row$title)) {
    table_title <- paste0(table_title, " ", config_row$title)
  }
  if (!is_empty(config_row$pop)) {
    table_title <- paste0(table_title, " - ", config_row$pop)
  }
  doc <- body_add_par(doc, table_title, style = "heading 2")

  # 添加"格式同表XX"
  ref_text <- paste0("格式同", ref_tfl)
  doc <- body_add_par(doc, ref_text, style = "Normal")

  # 添加脚注
  footnotes <- c()
  for (i in 1:7) {
    fn_col <- paste0("footnote", i)
    if (fn_col %in% colnames(config_row) && !is.na(config_row[[fn_col]])) {
      footnotes <- c(footnotes, config_row[[fn_col]])
    }
  }

  if (length(footnotes) > 0) {
    fn_text <- paste("注：", paste(footnotes, collapse = " "))
    doc <- body_add_rich_par(doc, fn_text, style = "Normal")
  }

  # 添加编程说明
  if (!is_empty(config_row$PgmNotes)) {
    pgm_text <- paste("编程说明：", config_row$PgmNotes)
    doc <- body_add_rich_par(doc, pgm_text, style = "Normal",
                              font_family = "宋体", font_size = 10.5, color = "blue")
  }

  return(doc)
}

#' 添加图形到Word文档
add_figure_to_doc <- function(doc, config_row, datasets, displayed_sections = c()) {

  # 获取数据集
  dataset_name <- config_row$Datasets
  if (is.null(datasets[[dataset_name]])) {
    cat(sprintf("  警告：未找到数据集 %s\n", dataset_name))
    return(doc)
  }

  dataset <- datasets[[dataset_name]]

  # 添加章节标题
  section_no <- config_row$`Section no`
  if (!is_empty(section_no) && !is_empty(config_row$`Section title`)) {
    if (!section_no %in% displayed_sections) {
      section_text <- paste0(section_no, " ", config_row$`Section title`)
      doc <- body_add_par(doc, section_text, style = "heading 1")
    }
  }

  # 添加图标题（cat + table no + title - pop）
  fig_title <- ""
  if (!is_empty(config_row$cat)) {
    fig_title <- paste0(config_row$cat, config_row$`table no`)
  } else {
    fig_title <- config_row$`table no`
  }
  if (!is_empty(config_row$title)) {
    fig_title <- paste0(fig_title, " ", config_row$title)
  }
  if (!is_empty(config_row$pop)) {
    fig_title <- paste0(fig_title, " - ", config_row$pop)
  }
  doc <- body_add_par(doc, fig_title, style = "heading 2")

  # 根据MacVar类型生成图形
  img_file <- NULL
  if (tolower(config_row$MacVar) == "kmplot") {
    img_file <- create_kmplot(dataset,
                             title = config_row$title,
                             xlab = "时间（月）",
                             ylab = "生存率")
  } else if (tolower(config_row$MacVar) == "swimplot") {
    img_file <- create_swimplot(dataset,
                               title = config_row$title,
                               xlab = "时间（周）")
  } else if (tolower(config_row$MacVar) == "waterfallplot") {
    img_file <- create_waterfallplot(dataset,
                                    title = config_row$title,
                                    ylab = "肿瘤负荷变化 (%)")
  } else if (tolower(config_row$MacVar) == "spiderplot") {
    img_file <- create_spiderplot(dataset,
                                 title = config_row$title,
                                 xlab = "时间（周）",
                                 ylab = "肿瘤负荷变化 (%)")
  } else if (tolower(config_row$MacVar) == "seriesplot") {
    img_file <- create_seriesplot(dataset,
                                 title = config_row$title,
                                 xlab = "时间",
                                 ylab = "测量值")
  } else if (tolower(config_row$MacVar) == "forestplot") {
    img_file <- create_forestplot(dataset,
                                 title = config_row$title)
  }

  # 插入图片
  if (!is.null(img_file) && file.exists(img_file)) {
    doc <- body_add_img(doc, src = img_file, width = 6, height = 4.5)
    # 删除临时文件
    unlink(img_file)
  }

  # 添加脚注
  footnotes <- c()
  for (i in 1:7) {
    fn_col <- paste0("footnote", i)
    if (fn_col %in% colnames(config_row) && !is.na(config_row[[fn_col]])) {
      footnotes <- c(footnotes, config_row[[fn_col]])
    }
  }

  if (length(footnotes) > 0) {
    fn_text <- paste("注：", paste(footnotes, collapse = " "))
    doc <- body_add_rich_par(doc, fn_text, style = "Normal")
  }

  return(doc)
}
