# R/utils/parse_word_to_yaml.R
# Parses a TFL Shell Word document into a draft config+datasets YAML.

.parse_config_rows <- function(summary) list()
.parse_datasets    <- function(summary, config) list()

parse_word_to_yaml <- function(word_file, output_yaml = NULL) {
  if (!requireNamespace("officer", quietly = TRUE)) stop("officer package required")
  if (!requireNamespace("yaml",    quietly = TRUE)) stop("yaml package required")

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

# Expose internals for testing
shell_tool_env <- environment(parse_word_to_yaml)
