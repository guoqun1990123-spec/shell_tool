# Word → YAML Config Parser Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Parse an existing TFL Shell Word (.docx) document and auto-generate `config` + `datasets` YAML, ready for human fine-tuning.

**Architecture:** Use `officer::docx_summary()` to flatten the Word document into a data.frame of paragraphs and table cells, then apply heuristics (title prefix, table position, indentation level) to reconstruct config rows and datasets entries, and finally serialize to YAML via the `yaml` package.

**Tech Stack:** R, `officer` (docx_summary), `yaml`, `dplyr` — all already in the project.

---

## Context

A statistician has an existing TFL Shell Word document (横向A4, 三线表, footnotes under tables). The goal is to reduce manual config entry: parse the Word file to produce a draft YAML that matches the schema expected by `read_yaml_input()` in `R/utils/read_yaml_config.R`, then let the user fine-tune.

Output YAML must pass `read_yaml_input()` validation (SeqNum, Section no, MacVar required; Datasets reference must exist).

---

## Key Files

- **Create:** `R/utils/parse_word_to_yaml.R` — main parser, exports `parse_word_to_yaml(word_file, output_yaml)`
- **Create:** `tests/test_parse_word_to_yaml.R` — tests (manual source-and-run style, no testthat dependency)
- **Create:** `examples/sample_shell.docx` — minimal test Word file with 2 tables + 1 figure entry
- **Reference (do not modify):**
  - `R/utils/read_yaml_config.R` — target schema + validation rules
  - `config/config_sample.yaml` — reference YAML format
  - `R/assemble_document.R` — shows how officer builds the structure we need to reverse

---

## Parsing Heuristics (apply in order)

### MacVar inference from title prefix
| Title starts with | MacVar |
|---|---|
| 表 / Table | PStab |
| 图 / Figure / Fig | KMplot (default; user adjusts sub-type) |
| 列表 / Listing / List | RptList |
| 附表 | PStab |
| anything else | PStab (fallback) |

### Table role detection
In `docx_summary()` output, `table_index` groups cells. Within a TFL block:
- **First table encountered** = TFL data table → becomes a `datasets` entry
- Tables after a `---` line or after a gap of >1 paragraph = new TFL block

### Column structure inference
For each data table (PStab):
- `row_id == 1` → header row → `Trtlab` (pipe-join non-empty cells, skip label col)
- `cell_id == 1, row_id > 1` → Label column
- `cell_id > 1, row_id > 1` → Aval (use first non-empty cell per row as representative)
- Bold label or ALL-CAPS → `Class` marker (insert blank Class row before group)
- Indentation detection: use `docx_summary(detailed=TRUE)` run data or fall back to leading spaces in text

### Section/table number extraction
Regex patterns (apply to paragraph text before each table):
```r
# Table number: "表14.1.1", "Table 14.1.1", "14.1.1"
tbl_no_pattern  <- "(?:表|Table\\s+)?(\\d+\\.\\d+\\.\\d+(?:\\.\\d+)?)"
# Section number: "11.1 人口学" → "11.1"
sec_no_pattern  <- "^(\\d+(?:\\.\\d+)*)"
```

### Population (pop) extraction
Scan title text for known tokens:
```r
pop_map <- list(FAS="全分析集|FAS", PPS="符合方案集|PPS", SAF="安全集|SAF|安全性分析集")
```

### Footnote extraction
Paragraphs after the table with style containing "footnote" OR text starting with `注：|Note:|[a]|^[1]` patterns → `footnote1` … `footnote7`.

---

## Task 1: Scaffold the parser file

**Files:**
- Create: `R/utils/parse_word_to_yaml.R`

**Step 1: Write the file skeleton**

```r
# R/utils/parse_word_to_yaml.R
# Parses a TFL Shell Word document into a draft config+datasets YAML.

parse_word_to_yaml <- function(word_file, output_yaml = NULL) {
  if (!requireNamespace("officer", quietly = TRUE)) stop("officer package required")
  if (!requireNamespace("yaml",    quietly = TRUE)) stop("yaml package required")

  doc     <- officer::read_docx(word_file)
  summary <- officer::docx_summary(doc)

  config   <- .parse_config_rows(summary)
  datasets <- .parse_datasets(summary, config)

  result <- list(version = 1, config = config, datasets = datasets)

  if (!is.null(output_yaml)) {
    yaml::write_yaml(result, output_yaml,
                     handlers = list(logical = function(x) if(x) "true" else "false"))
    message("Written to: ", output_yaml)
  }
  invisible(result)
}
```

**Step 2: Verify file exists and sources without error**

```r
source("R/utils/parse_word_to_yaml.R")
# Expected: no error, parse_word_to_yaml is now defined
```

**Step 3: Commit**

```bash
git add R/utils/parse_word_to_yaml.R
git commit -m "feat: scaffold parse_word_to_yaml entry point"
```

---

## Task 2: Implement TFL block splitter

**Files:**
- Modify: `R/utils/parse_word_to_yaml.R` — add `.split_tfl_blocks(summary)`

**Step 1: Write failing test**

Create `tests/test_parse_word_to_yaml.R`:

```r
source("R/utils/parse_word_to_yaml.R")

# Minimal synthetic docx_summary data frame simulating 2 TFL blocks
fake_summary <- data.frame(
  doc_index    = 1:6,
  content_type = c("paragraph","paragraph","table cell","table cell","paragraph","paragraph"),
  style_name   = c("heading 2","Normal","Normal","Normal","heading 2","Normal"),
  text         = c("表14.1.1 受试者基线","",  "年龄","Mean","表14.1.2 安全性",""),
  table_index  = c(NA, NA, 1L, 1L, NA, NA),
  row_id       = c(NA, NA, 1L, 2L, NA, NA),
  cell_id      = c(NA, NA, 1L, 1L, NA, NA),
  stringsAsFactors = FALSE
)

blocks <- shell_tool_env$.split_tfl_blocks(fake_summary)
stopifnot(length(blocks) == 2)
cat("Task 2 test PASSED\n")
```

**Step 2: Run test — expect FAIL**

```r
source("tests/test_parse_word_to_yaml.R")
# Expected: Error — .split_tfl_blocks not found
```

**Step 3: Implement `.split_tfl_blocks()`**

Add to `parse_word_to_yaml.R`:

```r
# Returns a list of data.frames, one per TFL block.
# A new block starts when a paragraph matches a TFL title pattern
# (contains a table/figure/listing number like 14.x.x).
.split_tfl_blocks <- function(summary) {
  tfl_title_re <- "(?:表|图|列表|Table|Figure|Fig|Listing)[\\s\\u00a0]*(\\d+\\.\\d+)"
  is_tfl_title <- grepl(tfl_title_re, summary$text, perl = TRUE, ignore.case = TRUE) &
                  summary$content_type == "paragraph"

  block_id <- cumsum(is_tfl_title)
  # rows before any TFL title get block 0 — discard them
  block_id[block_id == 0] <- NA

  split(summary, block_id)
}
```

**Step 4: Export for testing** — wrap functions in an environment so tests can access internals:

```r
# At bottom of parse_word_to_yaml.R
shell_tool_env <- environment(parse_word_to_yaml)
```

**Step 5: Run test — expect PASS**

```r
source("R/utils/parse_word_to_yaml.R")
source("tests/test_parse_word_to_yaml.R")
# Expected: "Task 2 test PASSED"
```

**Step 6: Commit**

```bash
git add R/utils/parse_word_to_yaml.R tests/test_parse_word_to_yaml.R
git commit -m "feat: implement TFL block splitter"
```

---

## Task 3: Implement config row extractor

**Files:**
- Modify: `R/utils/parse_word_to_yaml.R` — add `.extract_config_row(block, seq_num)`
- Modify: `tests/test_parse_word_to_yaml.R` — add Task 3 test

**Step 1: Add test**

```r
# Task 3: config row extraction
block <- fake_summary[1:4, ]   # first 4 rows = heading + blank + 2 table cells
row   <- shell_tool_env$.extract_config_row(block, seq_num = 1L)

stopifnot(row$SeqNum    == 1)
stopifnot(row$MacVar    == "PStab")
stopifnot(grepl("14.1.1", row[["table no"]]))
cat("Task 3 test PASSED\n")
```

**Step 2: Run test — expect FAIL**

**Step 3: Implement `.extract_config_row()`**

```r
.extract_config_row <- function(block, seq_num) {
  paras <- block[block$content_type == "paragraph", ]
  title_text <- paras$text[nchar(trimws(paras$text)) > 0][1]
  if (is.na(title_text)) title_text <- ""

  # Extract table number
  tbl_no <- regmatches(title_text,
    regexpr("\\d+\\.\\d+\\.\\d+(?:\\.\\d+)?", title_text, perl = TRUE))
  if (length(tbl_no) == 0) tbl_no <- ""

  # Extract section number (leading digits like "11.1" or "14")
  sec_no <- regmatches(title_text,
    regexpr("^(\\d+(?:\\.\\d+)*)", trimws(title_text), perl = TRUE))
  if (length(sec_no) == 0) sec_no <- ""

  # Infer MacVar
  macvar <- .infer_macvar(title_text)

  # Infer Trtlab from table header row
  trtlab <- .extract_trtlab(block)

  # Infer pop
  pop <- .infer_pop(title_text)

  # Extract footnotes
  fns <- .extract_footnotes(block)

  data.frame(
    SeqNum          = seq_num,
    `Section no`    = sec_no,
    `Section title` = "",
    `table no`      = tbl_no,
    title           = title_text,
    pop             = pop,
    MacVar          = macvar,
    Datasets        = paste0("ds_", seq_num),   # placeholder, user renames
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
    ByseqL          = NA,
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
  if (grepl("全分析集|\\bFAS\\b", title_text)) return("FAS")
  if (grepl("符合方案集|\\bPPS\\b", title_text)) return("PPS")
  if (grepl("安全集|\\bSAF\\b|安全性分析集", title_text)) return("SAF")
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
  fn_re <- "^(?:注[：:]|Note[s]?[：:]|\\[\\w\\]|\\d+\\.|[a-z]\\))"
  fn_rows <- paras[grepl(fn_re, trimws(paras$text), ignore.case = TRUE, perl = TRUE), ]
  trimws(fn_rows$text)
}
```

**Step 4: Run test — expect PASS**

**Step 5: Commit**

```bash
git add R/utils/parse_word_to_yaml.R tests/test_parse_word_to_yaml.R
git commit -m "feat: implement config row extractor with MacVar/pop/footnote heuristics"
```

---

## Task 4: Implement datasets extractor

**Files:**
- Modify: `R/utils/parse_word_to_yaml.R` — add `.extract_dataset(block, ds_name)`
- Modify: `tests/test_parse_word_to_yaml.R` — add Task 4 test

**Step 1: Add test**

```r
# Task 4: datasets extraction
ds <- shell_tool_env$.extract_dataset(fake_summary[1:4,], "ds_1")
stopifnot(is.data.frame(ds))
stopifnot("Label" %in% names(ds))
stopifnot("Order" %in% names(ds))
stopifnot("Aval"  %in% names(ds))
cat("Task 4 test PASSED\n")
```

**Step 2: Run test — expect FAIL**

**Step 3: Implement `.extract_dataset()`**

```r
.extract_dataset <- function(block, ds_name) {
  cells <- block[!is.na(block$table_index), ]
  if (nrow(cells) == 0) {
    # Figure or listing block — return empty placeholder
    return(data.frame(Class="", Label="(图形，无数据行)", Order=0L,
                      Aval="", exclude=0L, BlankCol="",
                      stringsAsFactors=FALSE))
  }

  # Skip header row (row_id == 1)
  data_cells <- cells[cells$row_id > 1, ]

  rows <- lapply(unique(data_cells$row_id), function(rid) {
    row_cells <- data_cells[data_cells$row_id == rid, ]
    row_cells  <- row_cells[order(row_cells$cell_id), ]

    label_text <- if (nrow(row_cells) >= 1) trimws(row_cells$text[1]) else ""
    # Aval: paste cells 2..n with "|" separator (user can split later)
    aval_text  <- if (nrow(row_cells) >= 2) {
      paste(trimws(row_cells$text[-1]), collapse = "|")
    } else ""

    # Heuristic: detect Class rows — short all-caps or bold-looking (no sub-rows)
    is_class <- nchar(aval_text) == 0 && nchar(label_text) > 0

    # Order: count leading spaces as proxy for indent (officer collapses them but we try)
    leading_spaces <- nchar(label_text) - nchar(ltrimws(label_text))
    order_val <- min(as.integer(leading_spaces / 2), 5L)

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

# Helper: left-trim only
ltrimws <- function(x) sub("^\\s+", "", x)
```

**Step 4: Run test — expect PASS**

**Step 5: Commit**

```bash
git add R/utils/parse_word_to_yaml.R tests/test_parse_word_to_yaml.R
git commit -m "feat: implement datasets extractor from table cells"
```

---

## Task 5: Wire up `.parse_config_rows()` and `.parse_datasets()`

**Files:**
- Modify: `R/utils/parse_word_to_yaml.R` — implement the two internal functions called by entry point

**Step 1: Implement both wiring functions**

```r
.parse_config_rows <- function(summary) {
  blocks <- .split_tfl_blocks(summary)
  rows <- mapply(.extract_config_row, blocks, seq_along(blocks), SIMPLIFY = FALSE)
  do.call(rbind, rows)
}

.parse_datasets <- function(summary, config) {
  blocks <- .split_tfl_blocks(summary)
  ds_list <- mapply(function(block, ds_name) {
    .extract_dataset(block, ds_name)
  }, blocks, config$Datasets, SIMPLIFY = FALSE)
  names(ds_list) <- config$Datasets
  ds_list
}
```

**Step 2: Write integration test in tests file**

```r
# Task 5: end-to-end on synthetic data (no real Word file needed)
# Build a minimal real-looking summary frame
e2e_summary <- data.frame(
  doc_index    = 1:7,
  content_type = c("paragraph","table cell","table cell","table cell","paragraph","paragraph","paragraph"),
  style_name   = c("heading 2","Normal","Normal","Normal","Normal","Normal","Normal"),
  text         = c("表14.1.1 受试者基线特征（FAS）",
                   "指标","A组","B组",
                   "年龄（岁）",
                   "注：FAS=全分析集",
                   ""),
  table_index  = c(NA,1L,1L,1L,NA,NA,NA),
  row_id       = c(NA,1L,1L,1L,NA,NA,NA),
  cell_id      = c(NA,1L,2L,3L,NA,NA,NA),
  stringsAsFactors = FALSE
)

result <- list(
  version  = 1L,
  config   = shell_tool_env$.parse_config_rows(e2e_summary),
  datasets = shell_tool_env$.parse_datasets(e2e_summary,
               shell_tool_env$.parse_config_rows(e2e_summary))
)

stopifnot(nrow(result$config) == 1)
stopifnot(result$config$MacVar == "PStab")
stopifnot(result$config$Trtlab == "A组|B组")
stopifnot(!is.null(result$datasets[["ds_1"]]))
cat("Task 5 integration test PASSED\n")
```

**Step 3: Run test — expect PASS**

**Step 4: Commit**

```bash
git add R/utils/parse_word_to_yaml.R tests/test_parse_word_to_yaml.R
git commit -m "feat: wire up parse_config_rows and parse_datasets"
```

---

## Task 6: YAML serialization and round-trip validation

**Files:**
- Modify: `R/utils/parse_word_to_yaml.R` — ensure output passes `read_yaml_input()`
- Add integration check to `tests/test_parse_word_to_yaml.R`

**Step 1: Add round-trip test**

```r
# Task 6: serialize to YAML and read back with read_yaml_input
source("R/utils/read_yaml_config.R")

tmp <- tempfile(fileext = ".yaml")
parse_word_to_yaml_from_summary <- function(summary, output_yaml) {
  source("R/utils/parse_word_to_yaml.R")   # reload to pick up latest
  cfg  <- shell_tool_env$.parse_config_rows(summary)
  ds   <- shell_tool_env$.parse_datasets(summary, cfg)
  result <- list(version = 1L, config = cfg, datasets = ds)
  yaml::write_yaml(result, output_yaml)
  invisible(result)
}

parse_word_to_yaml_from_summary(e2e_summary, tmp)

# Must not throw
tryCatch({
  read_back <- read_yaml_input(tmp)
  stopifnot(nrow(read_back$config) == 1)
  cat("Task 6 round-trip PASSED\n")
}, error = function(e) {
  cat("Task 6 FAILED:", conditionMessage(e), "\n")
})
unlink(tmp)
```

**Step 2: Run test — fix any YAML structure issues until PASS**

Common fixes needed:
- `NA` values in YAML must be `~` or `null` — use `yaml` package handler
- Integer vs character coercion for `SeqNum`
- Ensure `list` key absent when no RptList entries (validator will complain if present but empty)

**Step 3: Commit**

```bash
git add R/utils/parse_word_to_yaml.R tests/test_parse_word_to_yaml.R
git commit -m "feat: YAML serialization passes read_yaml_input round-trip"
```

---

## Task 7: Real Word file smoke test

**Files:**
- Create: `examples/test_parse_word.R` — manual smoke test script

**Step 1: Create the smoke test script**

```r
# examples/test_parse_word.R
# Manual smoke test: run against a real Word Shell document.
# Usage: source("examples/test_parse_word.R")
setwd(dirname(rstudioapi::getSourceEditorContext()$path))
setwd("..")   # project root

source("R/utils/parse_word_to_yaml.R")

word_file  <- "examples/sample_shell.docx"   # replace with real file
output_yaml <- "output/parsed_config.yaml"

if (!file.exists(word_file)) {
  message("Place your TFL Shell .docx at: ", word_file)
} else {
  result <- parse_word_to_yaml(word_file, output_yaml)
  cat("Config rows parsed:", nrow(result$config), "\n")
  cat("Datasets extracted:", length(result$datasets), "\n")
  cat("Output written to:", output_yaml, "\n")
  cat("\nFirst config row:\n")
  print(t(result$config[1, ]))
}
```

**Step 2: Place a real (or anonymized) Word Shell at `examples/sample_shell.docx`**

Tip: If you don't have one, generate one with `generate_shell()` first, then parse it back — perfect sanity check.

**Step 3: Run and review `output/parsed_config.yaml`**

Inspect manually: table numbers extracted? Trtlab correct? Footnotes captured?

**Step 4: Commit**

```bash
git add examples/test_parse_word.R
git commit -m "test: add smoke test script for Word parser"
```

---

## Task 8: PDF support (optional, deferred)

> Skip unless user explicitly requests it. PDF parsing requires `pdftools` (text extraction) or OCR (`tesseract`) and produces far noisier output than docx_summary(). Recommend workflow: convert PDF → Word first using Word's built-in import, then run this parser.

If needed: `pdftools::pdf_text()` → split on page breaks → apply same regex heuristics as above on raw text lines.

---

## Verification (end-to-end)

```r
# 1. Source parser
source("R/utils/parse_word_to_yaml.R")

# 2. Run on your Shell Word file
parse_word_to_yaml("examples/sample_shell.docx", "output/draft_config.yaml")

# 3. Verify YAML is valid
source("R/utils/read_yaml_config.R")
cfg <- read_yaml_input("output/draft_config.yaml")
cat("Config rows:", nrow(cfg$config), "\n")

# 4. Generate Word output from parsed YAML (full round-trip)
source("R/generators/generate_shell.R")
generate_shell(
  config_file  = "output/draft_config.yaml",
  output_file  = "output/round_trip_shell.docx"
)
# Open round_trip_shell.docx and verify structure matches original
```

---

## Notes for fine-tuning after parsing

The parser produces **draft** YAML. Common manual adjustments:
1. Rename `Datasets` keys from `ds_1`, `ds_2` to meaningful names (e.g. `t_demo`)
2. Split `Aval` cell content — parser joins multi-column values with `|`; often only one representative value is needed
3. Adjust `Class` rows — bold detection is heuristic; verify group headers
4. Set correct `MacVar` for figures (parser defaults all figures to `KMplot`)
5. Fill in `Section title`, `pop`, `PgmNotes` fields that may be blank
