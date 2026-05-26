# 富文本解析模块
# 语法：^[文字] = 上标，_[文字] = 下标，其余为普通文本
# 示例："IC50^[a]_[b] [注释]" → "IC50" + 上标"a" + 下标"b" + " [注释]"

#' 解析富文本标记，返回 officer fpar 对象
#' @param text 含标记的字符串
#' @param base_prop fp_text 基础文本属性（字体、字号等）
#' @return fpar 对象，可直接用于 body_add_fpar
parse_rich_text_to_fpar <- function(text, base_prop = fp_text()) {
  chunks <- parse_rich_text_chunks(text)
  ftext_list <- lapply(chunks, function(chunk) {
    prop <- base_prop
    if (chunk$type == "super") {
      prop$vertical.align <- "superscript"
      prop$font.size <- (base_prop$font.size %||% 10.5) * 0.75
    } else if (chunk$type == "sub") {
      prop$vertical.align <- "subscript"
      prop$font.size <- (base_prop$font.size %||% 10.5) * 0.75
    }
    ftext(chunk$text, prop = prop)
  })
  do.call(fpar, ftext_list)
}

#' 解析富文本标记，返回 flextable as_paragraph 对象
#' @param text 含标记的字符串
#' @param base_size 基础字号（pt）
#' @return as_paragraph 对象，用于 flextable::compose
parse_rich_text_to_paragraph <- function(text, base_size = 10.5) {
  chunks <- parse_rich_text_chunks(text)
  chunk_list <- lapply(chunks, function(chunk) {
    if (chunk$type == "super") {
      as_sup(chunk$text)
    } else if (chunk$type == "sub") {
      as_sub(chunk$text)
    } else {
      as_chunk(chunk$text)
    }
  })
  do.call(as_paragraph, chunk_list)
}

#' 将文本解析为 chunk 列表
#' @param text 含标记的字符串
#' @return list，每项含 $type（"normal"/"super"/"sub"）和 $text
parse_rich_text_chunks <- function(text) {
  if (is.na(text) || nchar(text) == 0) {
    return(list(list(type = "normal", text = "")))
  }

  chunks <- list()
  remaining <- text

  while (nchar(remaining) > 0) {
    # 查找 ^[ 或 _[ 的位置
    super_pos <- regexpr("\\^\\[", remaining, fixed = FALSE)
    sub_pos   <- regexpr("_\\[",   remaining, fixed = FALSE)

    # 确定最先出现的标记
    first_pos <- NA
    first_type <- NA
    prefix_len <- NA

    if (super_pos > 0 && (is.na(first_pos) || super_pos < first_pos)) {
      first_pos  <- super_pos
      first_type <- "super"
      prefix_len <- 2  # "^["
    }
    if (sub_pos > 0 && (is.na(first_pos) || sub_pos < first_pos)) {
      first_pos  <- sub_pos
      first_type <- "sub"
      prefix_len <- 2  # "_["
    }

    if (is.na(first_pos)) {
      # 没有更多标记，剩余全部为普通文本
      chunks[[length(chunks) + 1]] <- list(type = "normal", text = remaining)
      break
    }

    # 提取标记前的普通文本
    if (first_pos > 1) {
      chunks[[length(chunks) + 1]] <- list(
        type = "normal",
        text = substr(remaining, 1, first_pos - 1)
      )
    }

    # 找到配对的 ]
    after_bracket <- substr(remaining, first_pos + prefix_len, nchar(remaining))
    close_pos <- regexpr("\\]", after_bracket, fixed = FALSE)

    if (close_pos < 0) {
      # 没有闭合括号，当作普通文本处理
      chunks[[length(chunks) + 1]] <- list(
        type = "normal",
        text = substr(remaining, first_pos, nchar(remaining))
      )
      break
    }

    inner_text <- substr(after_bracket, 1, close_pos - 1)
    chunks[[length(chunks) + 1]] <- list(type = first_type, text = inner_text)

    # 剩余文本
    remaining <- substr(after_bracket, close_pos + 1, nchar(after_bracket))
  }

  if (length(chunks) == 0) {
    chunks <- list(list(type = "normal", text = ""))
  }

  return(chunks)
}

#' 判断文本是否含有富文本标记
has_rich_text <- function(text) {
  if (is.na(text) || nchar(text) == 0) return(FALSE)
  grepl("\\^\\[|_\\[", text)
}

# R 4.1 以下没有 %||%，补充定义
`%||%` <- function(a, b) if (!is.null(a) && !is.na(a)) a else b
