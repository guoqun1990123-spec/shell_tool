# examples/test_parse_word.R
# Smoke test: parse output_shell_sample.docx and assert quality gates.
# Run:  Rscript examples/test_parse_word.R

source("R/utils/parse_word_to_yaml.R")
source("R/utils/read_yaml_config.R")

`%||%` <- function(a, b) if (is.null(a)) b else a

word_file   <- "output/output_shell_sample.docx"
output_yaml <- "output/parsed_config.yaml"

if (!file.exists(word_file)) {
  stop("Smoke test requires ", word_file,
       " — place a TFL Shell .docx there and retry.")
}

if (!dir.exists("output")) dir.create("output")

result <- parse_word_to_yaml(word_file, output_yaml)

cat("Config rows parsed:", length(result$config), "\n")
cat("Datasets extracted:", length(result$datasets), "\n")

# ── Assertion 1: Section no looks like "14.x" (not bare "14") ────────────────
sec_nos <- vapply(result$config, function(r) as.character(r[["Section no"]]), "")
well_formed <- sec_nos[nchar(sec_nos) > 0]
stopifnot(
  "At least one Section no must be '14.x' form (not just '14')" =
    any(grepl("^\\d+\\.\\d+", well_formed))
)
cat("Assertion 1 PASSED: Section no =", paste(head(well_formed, 3), collapse=", "), "\n")

# ── Assertion 2: No PAGEREF / \\h in titles ───────────────────────────────────
titles <- vapply(result$config, function(r) as.character(r$title %||% ""), "")
stopifnot(
  "title must not contain PAGEREF" =
    !any(grepl("PAGEREF", titles, fixed = TRUE)),
  "title must not contain \\h " =
    !any(grepl("\\h ", titles, fixed = TRUE))
)
cat("Assertion 2 PASSED: titles clean\n")

# ── Assertion 3: At least one non-empty Trtlab ───────────────────────────────
trtlabs <- vapply(result$config, function(r) as.character(r$Trtlab %||% ""), "")
stopifnot(
  "At least one Trtlab must be non-empty" =
    any(nchar(trtlabs) > 0L)
)
cat("Assertion 3 PASSED: Trtlab sample =", paste(head(trtlabs[nchar(trtlabs)>0], 2), collapse="; "), "\n")

# ── Assertion 4: datasets non-empty ──────────────────────────────────────────
stopifnot(
  "At least one dataset must be present" = length(result$datasets) >= 1L
)
first_ds <- result$datasets[[1L]]
stopifnot(
  "First dataset must have at least one row with non-empty Label" =
    any(vapply(first_ds, function(r) nchar(as.character(r$Label %||% "")) > 0L, logical(1L)))
)
cat("Assertion 4 PASSED: first dataset has", length(first_ds), "rows\n")

# ── Assertion 5: no .na.character in YAML output ─────────────────────────────
yaml_lines <- readLines(output_yaml, warn = FALSE)
stopifnot(
  "YAML must not contain .na.character" =
    !any(grepl(".na.character", yaml_lines, fixed = TRUE))
)
cat("Assertion 5 PASSED: YAML serialization clean\n")

# ── Assertion 6: read_yaml_input round-trip succeeds ─────────────────────────
tryCatch({
  rb <- read_yaml_input(output_yaml)
  stopifnot(nrow(rb$config) == length(result$config))
  cat("Assertion 6 PASSED: read_yaml_input loaded", nrow(rb$config), "rows\n")
}, error = function(e) {
  stop("Assertion 6 FAILED (read_yaml_input): ", conditionMessage(e))
})

cat("\nAll smoke-test assertions PASSED\n")
cat("Output written to:", output_yaml, "\n")
