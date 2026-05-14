# examples/test_parse_word.R
# Manual smoke test: parse a TFL Shell Word document into YAML.
#
# Usage (from RStudio or R console, with working dir = project root):
#   source("examples/test_parse_word.R")
#
# Or from command line:
#   Rscript -e "setwd('d:/shell_tool'); source('examples/test_parse_word.R')"

source("R/utils/parse_word_to_yaml.R")

word_file   <- "examples/sample_shell.docx"
output_yaml <- "output/parsed_config.yaml"

if (!file.exists(word_file)) {
  message("Smoke test skipped: place your TFL Shell .docx at: ", word_file)
  message("Tip: generate one first with generate_shell(), then parse it back as a sanity check.")
} else {
  if (!dir.exists("output")) dir.create("output")
  result <- parse_word_to_yaml(word_file, output_yaml)
  # result$config is a list of named lists (one per TFL entry)
  # result$datasets is a named list of dataset row-lists
  cat("Config rows parsed:", length(result$config), "\n")
  cat("Datasets extracted:", length(result$datasets), "\n")
  cat("Output written to:", output_yaml, "\n")
}
