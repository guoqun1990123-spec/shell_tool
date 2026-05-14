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
