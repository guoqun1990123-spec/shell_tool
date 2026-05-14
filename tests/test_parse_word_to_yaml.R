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

# Use a summary with a real data row (row_id=2) to exercise multi-row dataset serialization
e2e_summary2 <- data.frame(
  doc_index    = 1:9,
  content_type = c("paragraph",
                   "table cell","table cell","table cell",
                   "table cell","table cell","table cell",
                   "paragraph","paragraph"),
  style_name   = rep("Normal", 9),
  text         = c("表14.1.1 受试者基线特征（FAS）",
                   "指标","A组","B组",
                   "年龄（岁）","12","14",
                   "注：FAS=全分析集",""),
  table_index  = c(NA, 1L,1L,1L, 1L,1L,1L, NA,NA),
  row_id       = c(NA, 1L,1L,1L, 2L,2L,2L, NA,NA),
  cell_id      = c(NA, 1L,2L,3L, 1L,2L,3L, NA,NA),
  stringsAsFactors = FALSE
)
e2e_summary2$style_name[1] <- "heading 2"

cfg2 <- shell_tool_env$.parse_config_rows(e2e_summary2)
ds2  <- shell_tool_env$.parse_datasets(e2e_summary2, cfg2)

tmp_yaml2 <- tempfile(fileext = ".yaml")

tryCatch({
  # Use parse_word_to_yaml indirectly by calling the internals and writing
  config_list2   <- lapply(seq_len(nrow(cfg2)), function(i) as.list(cfg2[i, ]))
  datasets_list2 <- lapply(ds2, function(df) {
    lapply(seq_len(nrow(df)), function(i) as.list(df[i, ]))
  })
  yaml::write_yaml(list(version = 1L, config = config_list2, datasets = datasets_list2), tmp_yaml2)

  read_back2 <- read_yaml_input(tmp_yaml2)
  stopifnot(nrow(read_back2$config) == 1)
  stopifnot(is.data.frame(read_back2$datasets[["ds_1"]]))
  stopifnot(nrow(read_back2$datasets[["ds_1"]]) == 1)  # 1 data row (row_id==2 has Aval, so not Class)
  stopifnot(all(c("Class","Label","Order","Aval","exclude","BlankCol") %in%
                colnames(read_back2$datasets[["ds_1"]])))
  cat("Task 6 round-trip PASSED\n")
}, error = function(e) {
  cat("Task 6 FAILED:", conditionMessage(e), "\n")
  stop(e)
})
unlink(tmp_yaml2)
