.split_tfl_blocks <- function(summary) {
  tfl_title_re <-
    "(?:表|图|列表|Table|Figure|Fig|Listing)[\\s\\x{00A0}]*(\\d+\\.\\d+)"
  is_tfl_title <-
    grepl(tfl_title_re, summary$text, perl = TRUE,
          ignore.case = TRUE) &
    summary$content_type == "paragraph"

  block_id <- cumsum(is_tfl_title)
  block_id[block_id == 0] <- NA

  split(summary, block_id)
}

.extract_config_row <- function(block, seq_num) {
  paras <- block[block$content_type == "paragraph", ]
  title_text <- paras$text[nchar(trimws(paras$text)) > 0][1]
  if (is.na(title_text)) title_text <- ""

  tbl_no_match <- regexpr("\\d+\\.\\d+\\.\\d+(?:\\.\\d+)?", title_text, perl = TRUE)
  tbl_no <- if (tbl_no_match > 0) regmatches(title_text, tbl_no_match) else ""

  # Derive section number from table number (first segment before first dot)
  # Fallback: try matching a leading number in the title directly
  sec_no <- if (nchar(tbl_no) > 0) {
    sub("\\..*", "", tbl_no)
  } else {
    sec_no_match <- regexpr("\\d+(?:\\.\\d+)*", title_text, perl = TRUE)
    if (sec_no_match > 0) regmatches(title_text, sec_no_match) else ""
  }

  macvar  <- .infer_macvar(title_text)
  trtlab  <- .extract_trtlab(block)
  pop     <- .infer_pop(title_text)
  fns     <- .extract_footnotes(block)

  data.frame(
    SeqNum          = seq_num,
    `Section no`    = sec_no,
    `Section title` = "",
    `table no`      = tbl_no,
    title           = title_text,
    pop             = pop,
    MacVar          = macvar,
    Datasets        = paste0("ds_", seq_num),
    Trtlab          = trtlab,
    Subgrp          = "",
    Adcols          = "",
    Varlab          = "",
    Labparm         = "",
    footnote1       = if (length(fns) >= 1) fns[1] else "",
    footnote2       = if (length(fns) >= 2) fns[2] else "",
    footnote3       = if (length(fns) >= 3) fns[3] else "",
    footnote4       = if (length(fns) >= 4) fns[4] else "",
    footnote5       = if (length(fns) >= 5) fns[5] else "",
    footnote6       = if (length(fns) >= 6) fns[6] else "",
    footnote7       = if (length(fns) >= 7) fns[7] else "",
    PgmNotes        = "",
    ByseqL          = NA_character_,
    RefTFL          = "",
    check.names     = FALSE,
    stringsAsFactors = FALSE
  )
}

.infer_macvar <- function(title_text) {
  if (grepl("^(?:图|Figure|Fig)", title_text, ignore.case = TRUE, perl = TRUE)) return("KMplot")
  if (grepl("^(?:列表|Listing|List)", title_text, ignore.case = TRUE, perl = TRUE)) return("RptList")
  "PStab"
}

.infer_pop <- function(title_text) {
  if (grepl("全分析集|\\bFAS\\b", title_text, perl = TRUE)) return("FAS")
  if (grepl("符合方案集|\\bPPS\\b", title_text, perl = TRUE)) return("PPS")
  if (grepl("安全集|\\bSAF\\b|安全性分析集", title_text, perl = TRUE)) return("SAF")
  ""
}

.extract_trtlab <- function(block) {
  header_cells <- block[!is.na(block$row_id) & block$row_id == 1 & block$cell_id > 1, ]
  labels <- trimws(header_cells$text)
  labels <- labels[nchar(labels) > 0]
  if (length(labels) == 0) return("")
  paste(labels, collapse = "|")
}

.extract_footnotes <- function(block) {
  paras <- block[block$content_type == "paragraph", ]
  fn_re <- "^(?:注[：:]|Notes?[：:]|\\[\\w+\\]|\\d+\\.|[a-z]\\))"
  fn_rows <- paras[grepl(fn_re, trimws(paras$text), ignore.case = TRUE, perl = TRUE), ]
  trimws(fn_rows$text)
}

.ltrimws <- function(x) sub("^\\s+", "", x)

.extract_dataset <- function(block, ds_name) {
  cells <- block[!is.na(block$table_index), ]
  if (nrow(cells) == 0) {
    return(data.frame(
      Class = "", Label = "(图形/清单，无数据行)", Order = 0L,
      Aval = "", exclude = 0L, BlankCol = "",
      stringsAsFactors = FALSE
    ))
  }

  data_cells <- cells[cells$row_id > 1, ]
  if (nrow(data_cells) == 0) {
    return(data.frame(
      Class = "", Label = "", Order = 0L,
      Aval = "", exclude = 0L, BlankCol = "",
      stringsAsFactors = FALSE
    ))
  }

  tbl_row_keys <- unique(data_cells[, c("table_index", "row_id")])
  tbl_row_keys <- tbl_row_keys[order(tbl_row_keys$table_index, tbl_row_keys$row_id), ]

  rows <- lapply(seq_len(nrow(tbl_row_keys)), function(i) {
    tid <- tbl_row_keys$table_index[i]
    rid <- tbl_row_keys$row_id[i]
    rc  <- data_cells[data_cells$table_index == tid & data_cells$row_id == rid, ]
    rc  <- rc[order(rc$cell_id), ]

    label_text <- if (nrow(rc) >= 1) trimws(rc$text[1]) else ""
    aval_text  <- if (nrow(rc) >= 2) paste(trimws(rc$text[-1]), collapse = "|") else ""

    # Heuristic: rows with no value cells are treated as group headers (Class).
    # Blank value rows or single-column tables may be misclassified — review output.
    is_class  <- nchar(aval_text) == 0 && nchar(label_text) > 0
    n_leading <- nchar(label_text) - nchar(.ltrimws(label_text))
    order_val <- min(as.integer(n_leading / 2L), 5L)

    data.frame(
      Class    = if (is_class) label_text else "",
      Label    = if (is_class) "" else label_text,
      Order    = order_val,
      Aval     = aval_text,
      exclude  = 0L,
      BlankCol = "",
      stringsAsFactors = FALSE
    )
  })

  do.call(rbind, rows)
}

.parse_config_rows <- function(summary) list()
.parse_datasets    <- function(summary, config) list()

parse_word_to_yaml <- function(word_file, output_yaml = NULL) {
  if (!requireNamespace("officer", quietly = TRUE)) {
    stop("officer package required")
  }
  if (!requireNamespace("yaml", quietly = TRUE)) {
    stop("yaml package required")
  }

  doc     <- officer::read_docx(word_file)
  summary <- officer::docx_summary(doc)

  config   <- .parse_config_rows(summary)
  datasets <- .parse_datasets(summary, config)

  result <- list(version = 1, config = config, datasets = datasets)

  if (!is.null(output_yaml)) {
    yaml::write_yaml(result, output_yaml)
    message("Written to: ", output_yaml)
  }
  invisible(result)
}

shell_tool_env <- environment(parse_word_to_yaml)
