# tests/test_parse_word_to_yaml.R
# Manual test suite for parse_word_to_yaml. Run with:
#   setwd("d:/shell_tool"); source("tests/test_parse_word_to_yaml.R")

source("R/utils/parse_word_to_yaml.R")

# --- Shared test data ---
fake_summary <- data.frame(
  doc_index    = 1:6,
  content_type = c("paragraph","paragraph","table cell","table cell","paragraph","paragraph"),
  style_name   = c("heading 2","Normal","Normal","Normal","heading 2","Normal"),
  text         = c("表14.1.1 受试者基线","", "年龄","Mean","表14.1.2 安全性",""),
  table_index  = c(NA, NA, 1L, 1L, NA, NA),
  row_id       = c(NA, NA, 1L, 2L, NA, NA),
  cell_id      = c(NA, NA, 1L, 1L, NA, NA),
  stringsAsFactors = FALSE
)

# --- Task 2 test ---
blocks <- shell_tool_env$.split_tfl_blocks(fake_summary)
stopifnot(length(blocks) == 2)
stopifnot(nrow(blocks[[1]]) == 4)
stopifnot(nrow(blocks[[2]]) == 2)
# Non-paragraph rows with matching text should not create new blocks
table_only <- fake_summary[fake_summary$content_type == "table cell", ]
no_title_blocks <- shell_tool_env$.split_tfl_blocks(table_only)
stopifnot(length(no_title_blocks) == 0)
cat("Task 2 test PASSED\n")

# --- Task 3 test ---
block_1 <- fake_summary[fake_summary$doc_index %in% 1:4, ]
row <- shell_tool_env$.extract_config_row(block_1, seq_num = 1L)

stopifnot(row$SeqNum == 1)
stopifnot(row$MacVar == "PStab")
stopifnot(grepl("14.1.1", row[["table no"]]))
stopifnot(row[["Section no"]] == "14")
cat("Task 3 test PASSED\n")

# --- Task 4 test ---
ds <- shell_tool_env$.extract_dataset(fake_summary[1:4, ], "ds_1")
stopifnot(is.data.frame(ds))
stopifnot(all(c("Class", "Label", "Order", "Aval", "exclude", "BlankCol") %in% names(ds)))
# row_id > 1 only: row 4 is "Mean" with cell_id=1 (label col), no Aval → treated as Class
stopifnot(nrow(ds) >= 1)

# Figure/listing block (no table cells) → placeholder row
no_table_block <- fake_summary[fake_summary$content_type == "paragraph", ]
ds_empty <- shell_tool_env$.extract_dataset(no_table_block, "ds_fig")
stopifnot(nrow(ds_empty) == 1)
stopifnot(ds_empty$exclude == 0L)
cat("Task 4 test PASSED\n")

# --- Task 5 integration test ---
e2e_summary <- data.frame(
  doc_index    = 1:7,
  content_type = c("paragraph","table cell","table cell","table cell",
                   "paragraph","paragraph","paragraph"),
  style_name   = c("heading 2","Normal","Normal","Normal","Normal","Normal","Normal"),
  text         = c("表14.1.1 受试者基线特征（FAS）",
                   "指标","A组","B组",
                   "年龄（岁）",
                   "注：FAS=全分析集",
                   ""),
  table_index  = c(NA, 1L, 1L, 1L, NA, NA, NA),
  row_id       = c(NA, 1L, 1L, 1L, NA, NA, NA),
  cell_id      = c(NA, 1L, 2L, 3L, NA, NA, NA),
  stringsAsFactors = FALSE
)

cfg  <- shell_tool_env$.parse_config_rows(e2e_summary)
ds   <- shell_tool_env$.parse_datasets(e2e_summary, cfg)

stopifnot(nrow(cfg) == 1)
stopifnot(cfg$MacVar == "PStab")
stopifnot(cfg$Trtlab == "A组|B组")
stopifnot(cfg$footnote1 == "注：FAS=全分析集")
stopifnot(!is.null(ds[["ds_1"]]))
cat("Task 5 integration test PASSED\n")

# --- Task 6 round-trip test ---
source("R/utils/read_yaml_config.R")

tmp_yaml <- tempfile(fileext = ".yaml")
cfg_list <- lapply(seq_len(nrow(cfg)), function(i) as.list(cfg[i, ]))
result6  <- list(version = 1L, config = cfg_list, datasets = ds)
yaml::write_yaml(result6, tmp_yaml)

tryCatch({
  read_back <- read_yaml_input(tmp_yaml)
  stopifnot(nrow(read_back$config) == 1)
  stopifnot(read_back$config$MacVar[1] %in% c("PStab","pstab"))
  cat("Task 6 round-trip PASSED\n")
}, error = function(e) {
  cat("Task 6 FAILED:", conditionMessage(e), "\n")
  cat("YAML written to:", tmp_yaml, "\n")
  stop(e)
})
unlink(tmp_yaml)
