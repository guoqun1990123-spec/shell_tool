# 清单生成模块

#' 从list工作表中提取指定Byseq的清单数据
extract_listing_data <- function(list_data, byseq) {

  # 筛选指定Byseq的数据
  listing <- list_data[list_data$Byseq == byseq, ]
  listing <- listing[order(listing$Byorder), ]

  if (nrow(listing) == 0) {
    stop(sprintf("未找到Byseq=%s的清单数据", byseq))
  }

  return(listing)
}

#' 构建清单表格
build_listing_table <- function(listing_data) {

  # 过滤 exclude=1 的列
  if ("exclude" %in% colnames(listing_data)) {
    listing_data <- listing_data[is.na(listing_data$exclude) | listing_data$exclude != 1, ]
  }

  col_labels <- listing_data$Lvalable
  n_cols <- nrow(listing_data)

  if (n_cols == 0) {
    return(data.frame())
  }

  # 示例行：有 Values 字段时用其内容，否则空白
  if ("Values" %in% colnames(listing_data)) {
    example_vals <- as.character(listing_data$Values)
    example_vals[is.na(example_vals)] <- ""
  } else {
    example_vals <- rep("", n_cols)
  }

  result <- data.frame(matrix("", nrow = 2, ncol = n_cols))
  colnames(result) <- col_labels
  result[1, ] <- example_vals

  return(result)
}

#' 创建清单flextable（三线表格式）
create_listing_flextable <- function(data) {

  ft <- flextable(data)

  # 三线表边框
  ft <- border_remove(ft)
  ft <- hline_top(ft, border = fp_border(width = 1.5), part = "header")
  ft <- hline_bottom(ft, border = fp_border(width = 1.5), part = "header")
  ft <- hline_bottom(ft, border = fp_border(width = 1.5), part = "body")

  # 设置字体：中文宋体 + 英文Times New Roman，五号（10.5pt）
  ft <- flextable::font(ft, fontname = "宋体", part = "all")
  ft <- flextable::font(ft, fontname = "Times New Roman", part = "all", cs.family = "Times New Roman")
  ft <- flextable::fontsize(ft, size = 10.5, part = "all")

  # 设置对齐
  ft <- align(ft, align = "center", part = "all")

  # 设置行高
  ft <- height_all(ft, height = 0.25, part = "all")

  # 设置表格宽度为页面宽度
  ft <- width(ft, width = 10.11 / ncol(data))

  # 设置表格属性为自动调整窗口
  ft <- set_table_properties(ft, layout = "autofit", width = 1)

  return(ft)
}
