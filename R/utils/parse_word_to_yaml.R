# parse_word_to_yaml.R  (v2 — table-anchored block splitting)
#
# Public entry point: parse_word_to_yaml(word_file, output_yaml)
# Internal helpers are accessible via shell_tool_env for unit tests.

# ── TOC detection ─────────────────────────────────────────────────────────────

.is_toc_paragraph <- function(text, style) {
  # Vectorised: returns logical vector same length as text/style
  grepl("PAGEREF", text, fixed = TRUE) |
    grepl("\\\\h\\s*\\d+", text, perl = TRUE) |
    grepl("\\bTOC\\b", text, perl = TRUE) |
    (!is.na(style) & grepl("^(?:toc|目录|TOC)", style,
                            ignore.case = TRUE, perl = TRUE))
}

# ── Block splitting (table-anchored) ─────────────────────────────────────────

# Returns list of list(pre=df, tbl=df, post=df, table_id=int).
# One element per unique table_index found in summary (after TOC filtering).
.split_tfl_blocks <- function(summary) {
  # Filter TOC entries
  is_toc <- .is_toc_paragraph(summary$text, summary$style_name)
  summary <- summary[!is_toc, ]

  tids <- sort(unique(summary$table_index[!is.na(summary$table_index)]))
  if (length(tids) == 0L) return(list())

  para_rows <- summary[is.na(summary$table_index), ]

  lapply(seq_along(tids), function(k) {
    tid <- tids[k]
    tbl <- summary[!is.na(summary$table_index) & summary$table_index == tid, ]

    first_idx <- min(tbl$doc_index)
    last_idx  <- max(tbl$doc_index)

    pre_start <- if (k > 1L) {
      prev_tid  <- tids[k - 1L]
      max(summary$doc_index[!is.na(summary$table_index) &
                               summary$table_index == prev_tid]) + 1L
    } else {
      1L
    }

    post_end <- if (k < length(tids)) {
      next_tid  <- tids[k + 1L]
      min(summary$doc_index[!is.na(summary$table_index) &
                               summary$table_index == next_tid]) - 1L
    } else {
      max(summary$doc_index)
    }

    pre  <- para_rows[para_rows$doc_index >= pre_start &
                        para_rows$doc_index <  first_idx, ]
    post <- para_rows[para_rows$doc_index >  last_idx &
                        para_rows$doc_index <= post_end, ]

    list(pre = pre, tbl = tbl, post = post, table_id = tid)
  })
}

# ── Heading-2 / TFL title parsing ────────────────────────────────────────────

# Parses strings like "表 14.1.1 受试者分布 - SAF"
# Returns list(cat, table_no, title, pop) or NULL if no match.
.parse_heading2 <- function(text) {
  if (is.null(text) || length(text) != 1L || is.na(text)) return(NULL)
  m <- regexpr(
    paste0("^(表|图|列表|Table|Figure|Fig|Listing)",
           "[\\s\\x{00A0}]*(\\d+(?:\\.\\d+)+)\\s*(.*)"),
    text, perl = TRUE
  )
  if (m == -1L) return(NULL)

  starts  <- attr(m, "capture.start")
  lengths <- attr(m, "capture.length")

  cat_str   <- substr(text, starts[1], starts[1] + lengths[1] - 1L)
  table_no  <- substr(text, starts[2], starts[2] + lengths[2] - 1L)
  remainder <- trimws(substr(text, starts[3], starts[3] + lengths[3] - 1L))

  # Split on last " - " to separate title from pop annotation
  sep_pos <- gregexpr(" - ", remainder, fixed = TRUE)[[1L]]
  if (sep_pos[1L] == -1L) {
    title <- remainder
    pop   <- ""
  } else {
    last_sep <- tail(sep_pos, 1L)
    title <- trimws(substr(remainder, 1L, last_sep - 1L))
    pop   <- trimws(substr(remainder, last_sep + 3L, nchar(remainder)))
  }

  list(cat = cat_str, table_no = table_no, title = title, pop = pop)
}

# ── Block context helpers ─────────────────────────────────────────────────────

# Scans pre-paragraphs (last → first) for a valid TFL heading-2 line.
.find_heading2_for_block <- function(block) {
  pre <- block$pre
  for (i in rev(seq_len(nrow(pre)))) {
    parsed <- .parse_heading2(pre$text[i])
    if (!is.null(parsed)) return(parsed)
  }
  list(cat = "表", table_no = "", title = "", pop = "")
}

# Walks the full summary backwards from the table to find heading 1.
.find_section_for_table <- function(block, summary) {
  first_tbl_doc <- min(block$tbl$doc_index)
  paras_before  <- summary[is.na(summary$table_index) &
                              summary$doc_index < first_tbl_doc, ]

  h1_rows <- paras_before[!is.na(paras_before$style_name) &
                             tolower(paras_before$style_name) == "heading 1", ]

  if (nrow(h1_rows) == 0L) return(list(sec_no = "", sec_title = ""))

  h1_text <- h1_rows$text[nrow(h1_rows)]
  m       <- regexpr("\\d+(?:\\.\\d+)*", h1_text, perl = TRUE)
  sec_no  <- if (m > 0L) regmatches(h1_text, m) else ""
  sec_title <- trimws(sub("^\\s*\\d+(?:\\.\\d+)*\\s*", "", h1_text, perl = TRUE))

  list(sec_no = sec_no, sec_title = sec_title)
}

# ── Table header extraction ───────────────────────────────────────────────────

# Returns list(trtlab, subgrp) from the header row(s) of the table.
.extract_header <- function(tbl) {
  if (nrow(tbl) == 0L) return(list(trtlab = "", subgrp = ""))

  all_row_ids    <- sort(unique(tbl$row_id[!is.na(tbl$row_id)]))
  header_row_id  <- all_row_ids[1L]

  header1 <- tbl[!is.na(tbl$row_id) & tbl$row_id == header_row_id, ]
  header1 <- header1[order(header1$cell_id), ]
  labels1 <- trimws(header1$text)

  # Collapse col_span-duplicated cells
  if ("col_span" %in% names(header1)) {
    r       <- rle(labels1)
    labels1 <- r$values
  }

  # Skip the first (label/varlab) column
  data_labels <- labels1[seq(2L, length(labels1))]
  data_labels <- data_labels[nchar(data_labels) > 0L]
  trtlab      <- paste(data_labels, collapse = "|")

  # Check for a second header row (subgroup pattern)
  subgrp <- ""
  if (length(all_row_ids) >= 2L) {
    second_row_id <- all_row_ids[2L]
    header2 <- tbl[!is.na(tbl$row_id) & tbl$row_id == second_row_id, ]
    header2 <- header2[order(header2$cell_id), ]
    labels2 <- trimws(header2$text)
    if ("col_span" %in% names(header2)) {
      r2      <- rle(labels2)
      labels2 <- r2$values
    }
    data2 <- labels2[seq(2L, length(labels2))]
    data2 <- data2[nchar(data2) > 0L]
    # If row 2 has strictly more data cells, treat it as the subgroup row
    if (length(data2) > length(data_labels) && length(data_labels) > 0L) {
      n_sub  <- length(data2) / length(data_labels)
      subgrp <- paste(data2[seq_len(as.integer(n_sub))], collapse = "|")
    }
  }

  list(trtlab = trtlab, subgrp = subgrp)
}

# ── Table body extraction ─────────────────────────────────────────────────────

.ltrimws <- function(x) sub("^\\s+", "", x)

# Returns data.frame(Class, Label, Order, Aval, exclude, BlankCol).
.extract_body <- function(tbl) {
  if (nrow(tbl) == 0L) {
    return(data.frame(
      Class = "", Label = "(图形/清单，无数据行)", Order = 0L,
      Aval = "", exclude = 0L, BlankCol = "",
      stringsAsFactors = FALSE
    ))
  }

  all_row_ids   <- sort(unique(tbl$row_id[!is.na(tbl$row_id)]))
  header_row_id <- all_row_ids[1L]
  data_row_ids  <- all_row_ids[all_row_ids > header_row_id]

  if (length(data_row_ids) == 0L) {
    return(data.frame(
      Class = "", Label = "", Order = 0L,
      Aval = "", exclude = 0L, BlankCol = "",
      stringsAsFactors = FALSE
    ))
  }

  tbl_row_keys <- unique(tbl[tbl$row_id %in% data_row_ids,
                              c("table_index", "row_id")])
  tbl_row_keys <- tbl_row_keys[order(tbl_row_keys$table_index,
                                     tbl_row_keys$row_id), ]

  rows <- lapply(seq_len(nrow(tbl_row_keys)), function(i) {
    tid <- tbl_row_keys$table_index[i]
    rid <- tbl_row_keys$row_id[i]
    rc  <- tbl[!is.na(tbl$table_index) & tbl$table_index == tid &
                 tbl$row_id == rid, ]
    rc  <- rc[order(rc$cell_id), ]

    raw_text   <- if (nrow(rc) >= 1L) rc$text[1L] else ""
    label_text <- trimws(raw_text)
    aval_text  <- if (nrow(rc) >= 2L)
      paste(trimws(rc$text[-1L]), collapse = "|") else ""

    # Entirely empty rows are Class boundary markers — skip
    if (nchar(label_text) == 0L && nchar(aval_text) == 0L) return(NULL)

    leading_spaces <- nchar(raw_text) - nchar(.ltrimws(raw_text))
    order_val      <- min(as.integer(leading_spaces %/% 2L), 5L)
    is_class       <- nchar(aval_text) == 0L && nchar(label_text) > 0L

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

  rows <- Filter(Negate(is.null), rows)
  if (length(rows) == 0L) {
    return(data.frame(
      Class = "", Label = "", Order = 0L,
      Aval = "", exclude = 0L, BlankCol = "",
      stringsAsFactors = FALSE
    ))
  }
  do.call(rbind, rows)
}

# ── Post-table paragraph extraction ──────────────────────────────────────────

.extract_labparm <- function(block) {
  pre <- block$pre
  if (nrow(pre) == 0L) return("")
  for (i in rev(seq_len(nrow(pre)))) {
    raw <- pre$text[i]
    if (is.na(raw)) next
    txt <- trimws(raw)
    sty <- if (!is.na(pre$style_name[i])) pre$style_name[i] else ""
    if (nchar(txt) == 0L) next
    if (grepl("^heading", sty, ignore.case = TRUE)) next
    if (!is.null(.parse_heading2(txt))) next
    if (grepl("^(?:注[：:]|Notes?[：:]|\\d+\\.|[a-z]\\))", txt,
              perl = TRUE)) next
    return(txt)
  }
  ""
}

.extract_footnotes <- function(block) {
  post <- block$post
  if (nrow(post) == 0L) return(character(0L))
  texts    <- post$text
  texts[is.na(texts)] <- ""
  fn_re    <- "^(?:注[：:]|Notes?[：:]|\\[\\w+\\]|\\d+\\.|[a-z]\\))"
  fn_rows  <- post[grepl(fn_re, trimws(texts),
                         ignore.case = TRUE, perl = TRUE), ]
  trimws(fn_rows$text)
}

.extract_pgmnotes <- function(block) {
  post <- block$post
  if (nrow(post) == 0L) return("")
  texts <- post$text
  texts[is.na(texts)] <- ""
  pgm <- post[grepl("^编程说明[：:]", trimws(texts), perl = TRUE), ]
  if (nrow(pgm) == 0L) return("")
  trimws(pgm$text[1L])
}

# ── MacVar / pop inference ────────────────────────────────────────────────────

.FIGURE_MACVARS <- c("KMplot", "Swimplot", "WaterfallPlot",
                     "Spiderplot", "Seriesplot", "Forestplot")

.infer_macvar <- function(cat_str) {
  if (grepl("^(?:图|Figure|Fig)", cat_str,
            ignore.case = TRUE, perl = TRUE)) return("KMplot")
  if (grepl("^(?:列表|Listing|List)", cat_str,
            ignore.case = TRUE, perl = TRUE)) return("RptList")
  "PStab"
}

.infer_pop <- function(title_text) {
  if (grepl("全分析集|\\bFAS\\b|\\bITT\\b", title_text, perl = TRUE)) return("FAS")
  if (grepl("符合方案集|\\bPPS\\b",           title_text, perl = TRUE)) return("PPS")
  if (grepl("安全集|\\bSAF\\b|安全性分析集",  title_text, perl = TRUE)) return("SAF")
  ""
}

# ── Config row extraction (v2) ────────────────────────────────────────────────

.extract_config_row <- function(block, seq_num, summary) {
  h2   <- .find_heading2_for_block(block)
  sec  <- .find_section_for_table(block, summary)
  hdr  <- .extract_header(block$tbl)
  fns  <- .extract_footnotes(block)
  pgm  <- .extract_pgmnotes(block)
  labp <- .extract_labparm(block)

  cat_str  <- h2$cat
  table_no <- h2$table_no
  title    <- h2$title
  pop_h2   <- h2$pop

  # Section no: from heading 1 if available, else strip last segment of table no
  sec_no <- if (nchar(sec$sec_no) > 0L) {
    sec$sec_no
  } else if (nchar(table_no) > 0L) {
    sub("\\.[^.]+$", "", table_no)
  } else {
    ""
  }

  macvar <- .infer_macvar(cat_str)
  pop    <- if (nchar(pop_h2) > 0L) pop_h2 else .infer_pop(title)

  # Figure types need no dataset; RptList must reference the 'list' sheet
  ds_name <- if (macvar %in% .FIGURE_MACVARS) {
    ""
  } else if (macvar == "RptList") {
    "list"
  } else {
    paste0("ds_", seq_num)
  }

  data.frame(
    SeqNum            = seq_num,
    `Section no`      = sec_no,
    `Section title`   = sec$sec_title,
    cat               = cat_str,
    `table no`        = table_no,
    title             = title,
    pop               = pop,
    MacVar            = macvar,
    Datasets          = ds_name,
    Trtlab            = hdr$trtlab,
    Subgrp            = hdr$subgrp,
    Adcols            = "",
    Varlab            = "",
    Labparm           = labp,
    footnote1         = if (length(fns) >= 1L) fns[1L] else "",
    footnote2         = if (length(fns) >= 2L) fns[2L] else "",
    footnote3         = if (length(fns) >= 3L) fns[3L] else "",
    footnote4         = if (length(fns) >= 4L) fns[4L] else "",
    footnote5         = if (length(fns) >= 5L) fns[5L] else "",
    footnote6         = if (length(fns) >= 6L) fns[6L] else "",
    footnote7         = if (length(fns) >= 7L) fns[7L] else "",
    PgmNotes          = pgm,
    ByseqL            = NA_character_,
    RefTFL            = "",
    check.names       = FALSE,
    stringsAsFactors  = FALSE
  )
}

# ── Dataset extraction (v2) ───────────────────────────────────────────────────

.extract_dataset <- function(block, ds_name) {
  .extract_body(block$tbl)
}

# ── Wiring ────────────────────────────────────────────────────────────────────

.parse_config_rows <- function(summary) {
  blocks <- .split_tfl_blocks(summary)
  if (length(blocks) == 0L) return(data.frame())
  rows <- mapply(function(b, i) .extract_config_row(b, i, summary),
                 blocks, seq_along(blocks), SIMPLIFY = FALSE)
  do.call(rbind, rows)
}

.parse_datasets <- function(summary, config) {
  blocks   <- .split_tfl_blocks(summary)
  if (length(blocks) == 0L) return(list())
  ds_names <- config$Datasets

  ds_list <- list()
  for (k in seq_along(blocks)) {
    nm <- ds_names[k]
    if (nchar(nm) == 0L) next             # figure rows have no dataset
    if (nm %in% names(ds_list)) next      # RptList dedup: only build 'list' once
    ds_list[[nm]] <- .extract_dataset(blocks[[k]], nm)
  }

  # Ensure a 'list' stub exists if any RptList row was found
  if (any(config$MacVar == "RptList") && !"list" %in% names(ds_list)) {
    ds_list[["list"]] <- data.frame(
      ListName = "", Byseq = 1L, Byorder = 1L, Lvalable = "",
      stringsAsFactors = FALSE
    )
  }

  ds_list
}

# ── NA → NULL scrubbing for YAML serialization ───────────────────────────────

.scrub_for_yaml <- function(x) {
  if (is.list(x)) return(lapply(x, .scrub_for_yaml))
  if (length(x) == 1L && is.na(x)) return(NULL)
  x
}

# ── Public entry point ────────────────────────────────────────────────────────

#' Parse a Word TFL Shell document and emit a config YAML.
#'
#' @param word_file Path to .docx file.
#' @param output_yaml Optional output path; if NULL returns the list invisibly.
#' @return Invisibly: list(version, config, datasets)
parse_word_to_yaml <- function(word_file, output_yaml = NULL) {
  if (!requireNamespace("officer", quietly = TRUE)) stop("officer package required")
  if (!requireNamespace("yaml",    quietly = TRUE)) stop("yaml package required")

  doc     <- officer::read_docx(word_file)
  summary <- officer::docx_summary(doc)

  config   <- .parse_config_rows(summary)
  datasets <- .parse_datasets(summary, config)

  config_list <- if (is.data.frame(config) && nrow(config) > 0L) {
    lapply(seq_len(nrow(config)), function(i) .scrub_for_yaml(as.list(config[i, ])))
  } else {
    list()
  }

  datasets_list <- lapply(datasets, function(df) {
    lapply(seq_len(nrow(df)), function(i) .scrub_for_yaml(as.list(df[i, ])))
  })

  result <- list(version = 1L, config = config_list, datasets = datasets_list)

  if (!is.null(output_yaml)) {
    yaml::write_yaml(result, output_yaml)
    message("Written to: ", output_yaml)
  }
  invisible(result)
}

shell_tool_env <- environment(parse_word_to_yaml)
