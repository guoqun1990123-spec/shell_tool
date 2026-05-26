# 表格生成模块

# 安全判断：值是否为空（处理NULL/NA/空字符串）
is_empty <- function(x) {
  is.null(x) || length(x) == 0 || all(is.na(x)) || all(x == "")
}

#' 构建表格列头
build_table_header <- function(trtlab, subgrop = NULL, varlab = "指标", adcols = NULL) {

  # 解析治疗组标签
  trt_labels <- strsplit(trtlab, "\\|")[[1]]

  # 解析额外列
  extra_col_vars <- c()
  extra_col_labels <- c()
  if (!is_empty(adcols)) {
    extra_cols <- strsplit(adcols, "\\|")[[1]]
    for (ec in extra_cols) {
      if (grepl("/", ec)) {
        parts <- strsplit(ec, "/")[[1]]
        if (length(parts) == 2) {
          extra_col_vars <- c(extra_col_vars, trimws(parts[1]))
          extra_col_labels <- c(extra_col_labels, trimws(parts[2]))
        }
      } else {
        col_label <- trimws(ec)
        extra_col_vars <- c(extra_col_vars, col_label)
        extra_col_labels <- c(extra_col_labels, col_label)
      }
    }
  }

  # 解析子组标签
  sub_labels <- if (!is_empty(subgrop)) strsplit(subgrop, "\\|")[[1]] else NULL

  # 构建列名（用于data.frame）和列标签（用于表头显示）
  col_vars <- c()    # 实际列名
  col_labels <- c()  # 显示标签

  # 1. 额外列
  col_vars <- c(col_vars, extra_col_vars)
  col_labels <- c(col_labels, extra_col_labels)

  # 2. Label列
  col_vars <- c(col_vars, varlab)
  col_labels <- c(col_labels, varlab)

  # 3. 数据列
  if (!is_empty(sub_labels)) {
    for (trt in trt_labels) {
      for (sub in sub_labels) {
        col_name <- paste0(trt, "_", sub)
        col_vars <- c(col_vars, col_name)
        col_labels <- c(col_labels, sub)  # 第二行只显示子组标签
      }
    }
  } else {
    for (trt in trt_labels) {
      col_vars <- c(col_vars, trt)
      col_labels <- c(col_labels, trt)
    }
  }

  # 转换为单行data.frame（列名=col_vars，值=col_labels）
  # check.names=FALSE 防止 make.names() 把括号替换成点号
  header <- as.data.frame(
    as.list(setNames(col_labels, col_vars)),
    stringsAsFactors = FALSE,
    check.names = FALSE
  )

  # 附加子组信息，用于create_flextable构建两行表头
  attr(header, "trt_labels") <- trt_labels
  attr(header, "sub_labels") <- sub_labels
  attr(header, "extra_col_vars") <- extra_col_vars
  attr(header, "varlab") <- varlab

  return(header)
}

#' 生成表格数据（处理Class分组空行和额外列）
build_table_data <- function(dataset, header, varlab = "指标") {

  # 初始化结果列表
  result_rows <- list()
  spacer_rows <- c()  # 记录空行的行号（在结果中的位置）
  n_cols <- ncol(header)
  prev_class <- NA

  # 找到Label列的位置（就是varlab对应的列）
  label_col_idx <- which(colnames(header) == varlab)
  if (length(label_col_idx) == 0) {
    label_col_idx <- 1  # 默认第一列
  } else {
    label_col_idx <- label_col_idx[1]
  }

  # 遍历数据集，在不同Class之间插入空行
  for (i in 1:nrow(dataset)) {
    current_class <- dataset$Class[i]

    # 如果Class变化且不是第一行，插入空行
    if (!is.na(prev_class) && !is.na(current_class) && prev_class != current_class) {
      empty_row <- as.list(rep("", n_cols))
      names(empty_row) <- colnames(header)
      result_rows[[length(result_rows) + 1]] <- empty_row
      spacer_rows <- c(spacer_rows, length(result_rows))
    }

    # 添加当前行
    row_data <- list()

    # 遍历所有列
    for (col_idx in 1:n_cols) {
      col_name <- colnames(header)[col_idx]

      # 检查是否是Label列
      if (col_idx == label_col_idx) {
        # Label列：添加缩进
        indent <- ifelse(is.na(dataset$Order[i]), 0, dataset$Order[i])
        spaces <- paste(rep("  ", indent), collapse = "")
        row_data[[col_idx]] <- paste0(spaces, dataset$Label[i])
      } else if (col_name %in% colnames(dataset)) {
        # 额外列：从dataset读取
        row_data[[col_idx]] <- ifelse(is.na(dataset[[col_name]][i]), "", dataset[[col_name]][i])
      } else {
        # 数据列：填充Aval
        row_data[[col_idx]] <- dataset$Aval[i]
      }
    }

    names(row_data) <- colnames(header)

    # 处理BlankCol
    if (!is.na(dataset$BlankCol[i])) {
      blank_indices <- as.numeric(strsplit(gsub("\\|$", "", dataset$BlankCol[i]), "\\|")[[1]])
      for (idx in blank_indices) {
        if (idx <= n_cols && idx > 0) {
          row_data[[idx]] <- ""
        }
      }
    }

    result_rows[[length(result_rows) + 1]] <- row_data
    prev_class <- current_class
  }

  # 转换为数据框
  result <- do.call(rbind.data.frame, c(result_rows, stringsAsFactors = FALSE))
  colnames(result) <- colnames(header)
  attr(result, "spacer_rows") <- spacer_rows

  return(result)
}

#' 创建flextable对象（三线表格式）
create_flextable <- function(data, header, varlab = "指标") {

  # 创建flextable
  ft <- flextable(data)

  # 获取子组信息
  trt_labels <- attr(header, "trt_labels")
  sub_labels <- attr(header, "sub_labels")
  extra_col_vars <- attr(header, "extra_col_vars")

  if (!is_empty(sub_labels) && length(sub_labels) > 1) {
    # 有子组：构建两行表头
    n_extra <- length(extra_col_vars)
    n_trt <- length(trt_labels)
    n_sub <- length(sub_labels)

    # 构建两行表头数据框
    # 第一行：治疗组标签
    row1 <- c(rep("", n_extra + 1), rep(trt_labels, each = n_sub))
    # 第二行：子组标签
    row2 <- unlist(header[1, ])

    # 创建header数据框
    header_df <- data.frame(
      col_keys = colnames(data),
      row1 = row1,
      row2 = row2,
      stringsAsFactors = FALSE,
      check.names = FALSE
    )

    # 使用set_header_df设置表头
    ft <- set_header_df(ft, mapping = header_df, key = "col_keys")

    # 合并额外列和Label列（跨行）
    for (i in 1:(n_extra + 1)) {
      ft <- merge_v(ft, j = i, part = "header")
    }

    # 合并治疗组列（跨列）
    for (i in 1:n_trt) {
      col_start <- n_extra + 1 + (i - 1) * n_sub + 1
      col_end <- col_start + n_sub - 1
      ft <- merge_at(ft, i = 1, j = col_start:col_end, part = "header")
    }
  } else {
    # 无子组：单行表头
    header_labels <- setNames(as.list(unlist(header[1, ])), colnames(data))
    ft <- set_header_labels(ft, .list = header_labels)
  }

  # 三线表边框：只保留顶部、表头下方、底部三条粗线
  ft <- border_remove(ft)  # 先移除所有边框
  ft <- hline_top(ft, border = fp_border(width = 1.5), part = "header")      # 顶部粗线
  ft <- hline_bottom(ft, border = fp_border(width = 1.5), part = "header")   # 表头下方粗线
  ft <- hline_bottom(ft, border = fp_border(width = 1.5), part = "body")     # 底部粗线

  # 双行表头时：在第一行和第二行之间加细分隔线
  if (!is_empty(sub_labels) && length(sub_labels) > 1) {
    ft <- hline(ft, i = 1, border = fp_border(width = 0.75), part = "header")
  }

  # 设置字体：中文宋体 + 英文Times New Roman
  # 五号字体 = 10.5pt
  ft <- flextable::font(ft, fontname = "宋体", part = "all")
  ft <- flextable::font(ft, fontname = "Times New Roman", part = "all", cs.family = "Times New Roman")
  ft <- flextable::fontsize(ft, size = 10.5, part = "all")

  # 设置对齐
  # 找到varlab列的位置
  label_col_idx <- which(colnames(data) == varlab)
  if (length(label_col_idx) == 0) {
    label_col_idx <- 1
  } else {
    label_col_idx <- label_col_idx[1]
  }

  # 数据列从label列之后开始
  data_col_start <- label_col_idx + 1

  # 额外列和Label列左对齐（1到label_col_idx）
  if (label_col_idx >= 1) {
    ft <- align(ft, align = "left", part = "body", j = 1:label_col_idx)
  }

  # 数据列居中对齐（label_col_idx+1到最后）
  if (data_col_start <= ncol(data)) {
    ft <- align(ft, align = "center", part = "body", j = data_col_start:ncol(data))
  }

  # 表头居中
  ft <- align(ft, align = "center", part = "header")

  # 设置行高
  ft <- height_all(ft, height = 0.25, part = "all")

  # 空行（Class分隔行）压缩到最小高度
  spacer_rows <- attr(data, "spacer_rows")
  if (!is.null(spacer_rows) && length(spacer_rows) > 0) {
    ft <- height(ft, i = spacer_rows, height = 0.01, part = "body")
  }

  # 设置表格宽度为页面宽度（横向A4：11.69英寸 - 左右边距1.58英寸 = 10.11英寸）
  ft <- width(ft, width = 10.11 / ncol(data))

  # 设置表格属性为自动调整窗口
  ft <- set_table_properties(ft, layout = "autofit", width = 1)

  # 设置段前段后距离为0
  ft <- padding(ft, padding.top = 0, padding.bottom = 0, part = "all")

  # 应用富文本（上标/下标）到含标记的单元格和表头
  ft <- apply_rich_text_to_flextable(ft, data, header, base_size = 10.5)

  return(ft)
}

#' 对 flextable 中含富文本标记的单元格应用 compose（body + header）
apply_rich_text_to_flextable <- function(ft, data, header, base_size = 10.5) {

  # body 部分
  for (j in seq_len(ncol(data))) {
    for (i in seq_len(nrow(data))) {
      cell_val <- as.character(data[i, j])
      if (!is.na(cell_val) && has_rich_text(cell_val)) {
        ft <- compose(ft, i = i, j = j, part = "body",
                      value = parse_rich_text_to_paragraph(cell_val, base_size = base_size))
      }
    }
  }

  # header 部分：从 header 属性重建表头文本矩阵，直接按位置 compose
  trt_labels    <- attr(header, "trt_labels")
  sub_labels    <- attr(header, "sub_labels")
  extra_col_vars <- attr(header, "extra_col_vars")
  varlab        <- attr(header, "varlab")
  n_extra       <- length(extra_col_vars)
  n_cols        <- ncol(data)

  has_sub <- !is_empty(sub_labels) && length(sub_labels) > 1

  if (has_sub) {
    n_trt <- length(trt_labels)
    n_sub <- length(sub_labels)
    # 第一行：extra列=""，varlab列=""，治疗组列=trt_labels（每个重复n_sub次）
    row1 <- c(rep("", n_extra + 1), rep(trt_labels, each = n_sub))
    # 第二行：extra列标签，varlab，子组标签
    row2 <- unlist(header[1, ])

    header_matrix <- list(row1, row2)
    for (i in seq_along(header_matrix)) {
      for (j in seq_len(n_cols)) {
        cell_val <- as.character(header_matrix[[i]][j])
        if (!is.na(cell_val) && has_rich_text(cell_val)) {
          ft <- compose(ft, i = i, j = j, part = "header",
                        value = parse_rich_text_to_paragraph(cell_val, base_size = base_size))
        }
      }
    }
  } else {
    # 单行表头：直接从 header data.frame 第一行读取
    row1 <- unlist(header[1, ])
    for (j in seq_len(n_cols)) {
      cell_val <- as.character(row1[j])
      if (!is.na(cell_val) && has_rich_text(cell_val)) {
        ft <- compose(ft, i = 1, j = j, part = "header",
                      value = parse_rich_text_to_paragraph(cell_val, base_size = base_size))
      }
    }
  }

  return(ft)
}
