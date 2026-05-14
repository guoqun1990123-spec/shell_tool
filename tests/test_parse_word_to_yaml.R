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
