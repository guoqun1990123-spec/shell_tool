# tests/test_parse_word_to_yaml.R  (v2)
# Run with:  setwd("d:/shell_tool"); source("tests/test_parse_word_to_yaml.R")

source("R/utils/parse_word_to_yaml.R")
source("R/utils/read_yaml_config.R")

# ── Task 1: fixture helpers ───────────────────────────────────────────────────

.mk_para <- function(text, style = "Normal", doc_index) {
  data.frame(
    doc_index    = doc_index,
    content_type = "paragraph",
    style_name   = style,
    text         = text,
    table_index  = NA_integer_,
    row_id       = NA_integer_,
    cell_id      = NA_integer_,
    stringsAsFactors = FALSE
  )
}

.mk_cell <- function(text, table_index, row_id, cell_id, doc_index,
                     col_span = 1L) {
  data.frame(
    doc_index    = doc_index,
    content_type = "table cell",
    style_name   = NA_character_,
    text         = text,
    table_index  = as.integer(table_index),
    row_id       = as.integer(row_id),
    cell_id      = as.integer(cell_id),
    col_span     = as.integer(col_span),
    stringsAsFactors = FALSE
  )
}

.mk_summary <- function(...) {
  rows <- list(...)
  # Align columns (col_span may be absent in para rows)
  all_cols <- unique(unlist(lapply(rows, names)))
  rows2 <- lapply(rows, function(r) {
    missing <- setdiff(all_cols, names(r))
    for (col in missing) r[[col]] <- NA
    r[all_cols]
  })
  do.call(rbind, lapply(rows2, as.data.frame, stringsAsFactors = FALSE))
}

cat("Task 1 (fixture helpers) READY\n")

# ── Task 2: TOC filtering + table-anchored block splitting ───────────────────

# Build summary: TOC para, heading1, heading2, table, footnote
toc_summary <- .mk_summary(
  .mk_para("表 14.1.1 受试者\\t PAGEREF _Toc123 \\h 4", "toc 1",  1L),
  .mk_para("14 人口学",                                  "heading 1", 2L),
  .mk_para("表14.1.1 受试者分布 - FAS",                  "heading 2", 3L),
  .mk_cell("指标",  1L, 1L, 1L, 4L),
  .mk_cell("A组",   1L, 1L, 2L, 4L),
  .mk_cell("年龄",  1L, 2L, 1L, 5L),
  .mk_cell("12",    1L, 2L, 2L, 5L),
  .mk_para("注：FAS=全分析集", "Normal", 6L)
)

blocks2 <- shell_tool_env$.split_tfl_blocks(toc_summary)

# TOC paragraph must be filtered out → only 1 table → 1 block
stopifnot(length(blocks2) == 1L)
# Block has the correct shape
b <- blocks2[[1L]]
stopifnot(all(c("pre", "tbl", "post", "table_id") %in% names(b)))
# pre has heading1 + heading2 (TOC para gone)
stopifnot(nrow(b$pre) == 2L)
# tbl has both data rows (different doc_index values)
stopifnot(nrow(b$tbl) == 4L)
# post has footnote
stopifnot(nrow(b$post) == 1L)
stopifnot(grepl("FAS", b$post$text[1L]))

# Summary with no tables → 0 blocks
no_tbl <- .mk_summary(.mk_para("只有段落", "Normal", 1L))
stopifnot(length(shell_tool_env$.split_tfl_blocks(no_tbl)) == 0L)

cat("Task 2 (block splitting) PASSED\n")

# ── Task 3 / Task 4: .parse_heading2 ─────────────────────────────────────────

env <- shell_tool_env

h1 <- env$.parse_heading2("表14.1.1 受试者分布 - FAS")
stopifnot(!is.null(h1))
stopifnot(h1$cat == "表")
stopifnot(h1$table_no == "14.1.1")
stopifnot(h1$title == "受试者分布")
stopifnot(h1$pop == "FAS")

h2 <- env$.parse_heading2("Figure 14.2.1 Kaplan-Meier - SAF")
stopifnot(!is.null(h2))
stopifnot(h2$table_no == "14.2.1")
stopifnot(h2$pop == "SAF")

# No match → NULL
stopifnot(is.null(env$.parse_heading2("这不是TFL标题")))
# No " - " separator → pop = ""
h3 <- env$.parse_heading2("表14.1.2 安全性汇总")
stopifnot(h3$pop == "")
stopifnot(h3$title == "安全性汇总")

cat("Task 3/4 (.parse_heading2) PASSED\n")

# ── Task 5: .extract_config_row + .extract_dataset ───────────────────────────

cfg_row <- env$.extract_config_row(b, 1L, toc_summary)
stopifnot(cfg_row$SeqNum == 1L)
stopifnot(cfg_row$MacVar == "PStab")
stopifnot(cfg_row[["table no"]] == "14.1.1")
stopifnot(cfg_row[["Section no"]] == "14")   # from heading 1
stopifnot(cfg_row$Trtlab == "A组")            # single treatment col (skip 指标)
stopifnot(cfg_row$footnote1 == "注：FAS=全分析集")
stopifnot(cfg_row$pop == "FAS")

ds1 <- env$.extract_dataset(b, "ds_1")
stopifnot(is.data.frame(ds1))
stopifnot(all(c("Class", "Label", "Order", "Aval", "exclude", "BlankCol") %in% names(ds1)))
stopifnot(nrow(ds1) >= 1L)
stopifnot(any(nchar(ds1$Label) > 0L))

cat("Task 5 (.extract_config_row / .extract_dataset) PASSED\n")

# ── Task 6: .extract_header — col_span dedup ─────────────────────────────────

# Simulate a table where "A组" spans 2 columns (col_span=2, appears twice)
span_summary <- .mk_summary(
  .mk_para("表14.3.1 疗效 - SAF", "heading 2", 1L),
  .mk_cell("指标",  1L, 1L, 1L, 2L, col_span = 1L),
  .mk_cell("A组",   1L, 1L, 2L, 2L, col_span = 2L),
  .mk_cell("A组",   1L, 1L, 3L, 2L, col_span = 2L),   # duplicate from span
  .mk_cell("B组",   1L, 1L, 4L, 2L, col_span = 2L),
  .mk_cell("B组",   1L, 1L, 5L, 2L, col_span = 2L),   # duplicate from span
  .mk_cell("数据",  1L, 2L, 1L, 3L),
  .mk_cell("1",     1L, 2L, 2L, 3L),
  .mk_cell("2",     1L, 2L, 3L, 3L),
  .mk_cell("3",     1L, 2L, 4L, 3L),
  .mk_cell("4",     1L, 2L, 5L, 3L)
)
blocks_span <- env$.split_tfl_blocks(span_summary)
hdr_span    <- env$.extract_header(blocks_span[[1L]]$tbl)
# After dedup: labels1 = c("指标","A组","B组") → trtlab = "A组|B组"
stopifnot(hdr_span$trtlab == "A组|B组")

cat("Task 6 (.extract_header col_span dedup) PASSED\n")

# ── Task 7: .extract_body — Class boundaries + Order ─────────────────────────

body_summary <- .mk_summary(
  .mk_para("表14.1.1 受试者", "heading 2", 1L),
  .mk_cell("指标",          1L, 1L, 1L, 2L),
  .mk_cell("A组",           1L, 1L, 2L, 2L),
  # Empty row (Class boundary between groups)
  .mk_cell("",              1L, 2L, 1L, 3L),
  .mk_cell("",              1L, 2L, 2L, 3L),
  # Group header row (no Aval → Class)
  .mk_cell("基线特征",      1L, 3L, 1L, 4L),
  # Data rows with indentation
  .mk_cell("  年龄",        1L, 4L, 1L, 5L),
  .mk_cell("12",            1L, 4L, 2L, 5L),
  .mk_cell("    均值",      1L, 5L, 1L, 6L),
  .mk_cell("34",            1L, 5L, 2L, 6L)
)
blocks_body <- env$.split_tfl_blocks(body_summary)
body_df     <- env$.extract_body(blocks_body[[1L]]$tbl)

# Empty row should be skipped; Class row detected
stopifnot(any(nchar(body_df$Class) > 0L))
# "  年龄" → Order = 1
age_row <- body_df[trimws(body_df$Label) == "年龄", ]
stopifnot(nrow(age_row) == 1L)
stopifnot(age_row$Order == 1L)
# "    均值" → Order = 2
mean_row <- body_df[trimws(body_df$Label) == "均值", ]
stopifnot(nrow(mean_row) == 1L)
stopifnot(mean_row$Order == 2L)

cat("Task 7 (.extract_body) PASSED\n")

# ── Task 8: integration (.parse_config_rows / .parse_datasets) ───────────────

e2e_summary <- .mk_summary(
  .mk_para("14 人口学及基线特征", "heading 1", 1L),
  .mk_para("表14.1.1 受试者基线特征 - FAS", "heading 2", 2L),
  .mk_cell("指标",     1L, 1L, 1L, 3L),
  .mk_cell("A组",      1L, 1L, 2L, 3L),
  .mk_cell("B组",      1L, 1L, 3L, 3L),
  .mk_cell("年龄（岁）",1L, 2L, 1L, 4L),
  .mk_cell("12",       1L, 2L, 2L, 4L),
  .mk_cell("14",       1L, 2L, 3L, 4L),
  .mk_para("注：FAS=全分析集", "Normal", 5L)
)

cfg  <- env$.parse_config_rows(e2e_summary)
dsets <- env$.parse_datasets(e2e_summary, cfg)

stopifnot(nrow(cfg) == 1L)
stopifnot(cfg$MacVar == "PStab")
stopifnot(cfg$Trtlab == "A组|B组")
stopifnot(cfg$footnote1 == "注：FAS=全分析集")
stopifnot(cfg[["Section no"]] == "14")
stopifnot(!is.null(dsets[["ds_1"]]))
stopifnot(nrow(dsets[["ds_1"]]) >= 1L)

cat("Task 8 (integration) PASSED\n")

# ── Task 9: .scrub_for_yaml (NA → NULL) ──────────────────────────────────────

scrubbed <- env$.scrub_for_yaml(list(a = 1L, b = NA, c = "x", d = NA_character_))
stopifnot(scrubbed$a == 1L)
stopifnot(is.null(scrubbed$b))
stopifnot(scrubbed$c == "x")
stopifnot(is.null(scrubbed$d))

cat("Task 9 (.scrub_for_yaml) PASSED\n")

# ── Task 10: YAML round-trip via read_yaml_input ──────────────────────────────

tmp <- tempfile(fileext = ".yaml")

tryCatch({
  config_list   <- lapply(seq_len(nrow(cfg)), function(i)
    env$.scrub_for_yaml(as.list(cfg[i, ])))
  datasets_list <- lapply(dsets, function(df)
    lapply(seq_len(nrow(df)), function(i)
      env$.scrub_for_yaml(as.list(df[i, ]))))

  yaml::write_yaml(list(version = 1L, config = config_list,
                        datasets = datasets_list), tmp)

  rb <- read_yaml_input(tmp)
  stopifnot(nrow(rb$config) == 1L)
  stopifnot(is.data.frame(rb$datasets[["ds_1"]]))
  stopifnot(nrow(rb$datasets[["ds_1"]]) >= 1L)
  stopifnot(all(c("Class", "Label", "Order", "Aval", "exclude", "BlankCol") %in%
                  colnames(rb$datasets[["ds_1"]])))

  # No .na.character in the raw YAML text
  yaml_text <- readLines(tmp, warn = FALSE)
  stopifnot(!any(grepl(".na.character", yaml_text, fixed = TRUE)))

  cat("Task 10 (YAML round-trip) PASSED\n")
}, error = function(e) {
  cat("Task 10 FAILED:", conditionMessage(e), "\n")
  stop(e)
}, finally = {
  unlink(tmp)
})

cat("\nAll tests PASSED\n")
