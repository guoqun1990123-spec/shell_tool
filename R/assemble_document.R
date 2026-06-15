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

#' 插入红色错误占位段落（generate_shell.R tryCatch 容错时调用）
#' @param doc officer 文档对象
#' @param row  当前 config 行（用于提取 table no / title 做提示）
#' @param msg  错误信息字符串
add_error_placeholder <- function(doc, row, msg) {
  tbl_no <- if (!is_empty(row$`table no`)) as.character(row$`table no`) else "?"
  title  <- if (!is_empty(row$title))      as.character(row$title)      else ""
  label  <- if (nchar(title) > 0) paste(tbl_no, title, sep = " ") else tbl_no
  # 截断超长错误信息，防止段落撑大文档
  short_msg <- substr(msg, 1, 200)
  text <- paste0("⚠ 此条生成失败 [", label, "]: ", short_msg)
  # 用红色 fp_text 渲染，body_add_fpar 不依赖 Word 段落样式中的颜色
  err_prop <- fp_text(font.size = 10.5, font.family = "宋体", color = "#CC0000")
  doc <- body_add_fpar(doc, fpar(ftext(text, err_prop)), style = "Normal")
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
    cat("  警告：mtext的RefTFL为空，将输出占位标题但无引用文字\n")
  } else {
    # 仅做存在性校验，查不到不中断渲染
    ref_row <- config[config$`table no` == ref_tfl & !is.na(config$`table no`), ]
    if (nrow(ref_row) == 0) {
      cat(sprintf("  警告：未找到引用的表格 %s\n", ref_tfl))
    }
  }

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

#' 读取 PNG IHDR 宽高像素（无外部依赖）
#' PNG 格式：签名8字节 + 长度4字节 + 类型4字节 + 宽4字节 + 高4字节（大端序）
#' @return c(width_px, height_px)，读取失败返回 c(800L, 600L)
.png_dims <- function(file) {
  tryCatch({
    con <- file(file, "rb")
    on.exit(close(con))
    raw_bytes <- readBin(con, what = "raw", n = 24)
    if (length(raw_bytes) < 24) return(c(800L, 600L))
    width  <- sum(as.integer(raw_bytes[17:20]) * c(16777216L, 65536L, 256L, 1L))
    height <- sum(as.integer(raw_bytes[21:24]) * c(16777216L, 65536L, 256L, 1L))
    c(width, height)
  }, error = function(e) c(800L, 600L))
}

#' 添加图形到Word文档
#' @param figures named list（table_no → base64 PNG），来自 YAML figures 块；
#'   命中时跳过 mock 生成，解码插入用户上传的真实图片。
add_figure_to_doc <- function(doc, config_row, datasets, figures = list(), displayed_sections = c()) {

  # 添加章节标题（仅当该章节首次出现时）
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

  # ── 图片来源：嵌入 base64 优先，否则生成 mock 示意图 ──────────────────
  tbl_no    <- as.character(config_row$`table no`)
  fig_b64   <- figures[[tbl_no]]
  img_file  <- NULL
  is_custom <- FALSE

  is_temp <- FALSE  # TRUE = 临时文件，插入后删除；FALSE = 磁盘持久文件，不删除

  if (!is.null(fig_b64) && nzchar(trimws(fig_b64))) {
    # 旧 YAML 兼容：base64 解码 → 临时 PNG
    if (!requireNamespace("base64enc", quietly = TRUE)) {
      cat("  警告：base64enc 包未安装，无法解码嵌入图片，改用 mock 示意图\n")
      cat("  请运行：install.packages('base64enc')\n")
    } else {
      img_bytes <- base64enc::base64decode(fig_b64)
      temp_path <- tempfile(fileext = ".png")
      writeBin(img_bytes, temp_path)
      img_file  <- temp_path
      is_custom <- TRUE
      is_temp   <- TRUE  # base64 解码产生的临时文件，用完即删
      cat(sprintf("  使用嵌入图片（%s）\n", tbl_no))
    }
  }

  # FigTemplate 覆盖：指定了模板文件名则用磁盘真实图（优先级低于 base64）
  if (!is_custom && !is_empty(config_row$FigTemplate)) {
    tmpl_path <- file.path("config", "Figures_template",
                           trimws(config_row$FigTemplate))
    if (file.exists(tmpl_path)) {
      img_file  <- tmpl_path
      is_custom <- TRUE
      is_temp   <- FALSE  # 磁盘模板文件，用完不删
      cat(sprintf("  使用模板图片（%s）\n", config_row$FigTemplate))
    } else {
      cat(sprintf("  警告：模板图 %s 不存在，改用合成示意图\n", tmpl_path))
    }
  }

  if (!is_custom) {
    # 无嵌入图片（或解码失败）：生成 mock 示意图
    dataset_name <- config_row$Datasets
    if (is.null(datasets[[dataset_name]])) {
      cat(sprintf("  警告：未找到数据集 %s，将使用内置示例数据\n", dataset_name))
    }
    dataset <- if (!is.null(datasets[[dataset_name]])) datasets[[dataset_name]] else data.frame()

    # 解析图形配置：Trtlab → 图例向量，Varlab → 轴标签
    fig_legend <- .fig_legend_labs(config_row$Trtlab)
    macvar_lc  <- tolower(config_row$MacVar)

    # 根据 MacVar 类型生成图形（轴标签优先读 Varlab，空则用各图默认值）
    if (macvar_lc == "kmplot") {
      ax <- .fig_axis_labels(config_row$Varlab, "时间（月）", "生存率")
      img_file <- create_kmplot(dataset,
                                title       = config_row$title,
                                xlab        = ax[1],
                                ylab        = ax[2],
                                legend_labs = fig_legend)
    } else if (macvar_lc == "swimplot") {
      ax <- .fig_axis_labels(config_row$Varlab, "时间（周）", "受试者")
      img_file <- create_swimplot(dataset,
                                  title       = config_row$title,
                                  xlab        = ax[1],
                                  ylab        = ax[2],
                                  legend_labs = fig_legend)
    } else if (macvar_lc == "waterfallplot") {
      ax <- .fig_axis_labels(config_row$Varlab, "受试者", "肿瘤负荷变化 (%)")
      img_file <- create_waterfallplot(dataset,
                                       title       = config_row$title,
                                       xlab        = ax[1],
                                       ylab        = ax[2],
                                       legend_labs = fig_legend)
    } else if (macvar_lc == "spiderplot") {
      ax <- .fig_axis_labels(config_row$Varlab, "时间（周）", "肿瘤负荷变化 (%)")
      img_file <- create_spiderplot(dataset,
                                    title       = config_row$title,
                                    xlab        = ax[1],
                                    ylab        = ax[2],
                                    legend_labs = fig_legend)
    } else if (macvar_lc == "seriesplot") {
      ax <- .fig_axis_labels(config_row$Varlab, "时间", "测量值")
      img_file <- create_seriesplot(dataset,
                                    title       = config_row$title,
                                    xlab        = ax[1],
                                    ylab        = ax[2],
                                    legend_labs = fig_legend)
    } else if (macvar_lc == "forestplot") {
      ax <- .fig_axis_labels(config_row$Varlab, "风险比 (95% CI)", "")
      img_file <- create_forestplot(dataset,
                                    title       = config_row$title,
                                    xlab        = ax[1],
                                    ylab        = ax[2],
                                    legend_labs = fig_legend)
    }
  }

  # 插入图片
  if (!is.null(img_file) && file.exists(img_file)) {
    if (is_custom) {
      # 嵌入图：按 PNG 真实宽高比等比缩放（最大宽 6in，最大高 7in）
      dims  <- .png_dims(img_file)
      max_w <- 6; max_h <- 7
      ratio <- dims[1] / max(dims[2], 1L)
      w     <- min(max_w, max_h * ratio)
      h     <- w / ratio
      doc <- body_add_img(doc, src = img_file, width = w, height = h)
    } else {
      # mock 示意图：固定 6×4.5（与 8×6 生成尺寸同为 4:3）
      doc <- body_add_img(doc, src = img_file, width = 6, height = 4.5)
      is_temp <- TRUE  # 合成示意图均为临时文件
    }
    if (is_temp) unlink(img_file)  # 仅删临时文件；磁盘模板图不删
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
