.split_tfl_blocks <- function(summary) {
  tfl_title_re <-
    "(?:表|图|列表|Table|Figure|Fig|Listing)[\\s\\x{00A0}]*(\\d+\\.\\d+)"
  is_tfl_title <-
    grepl(tfl_title_re, summary$text, perl = TRUE,
          ignore.case = TRUE) &
    summary$content_type == "paragraph"

  block_id <- cumsum(is_tfl_title)
  block_id[block_id == 0] <- NA

  split(summary, block_id)
}

.parse_config_rows <- function(summary) list()
.parse_datasets    <- function(summary, config) list()

parse_word_to_yaml <- function(word_file, output_yaml = NULL) {
  if (!requireNamespace("officer", quietly = TRUE)) {
    stop("officer package required")
  }
  if (!requireNamespace("yaml", quietly = TRUE)) {
    stop("yaml package required")
  }

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

shell_tool_env <- environment(parse_word_to_yaml)
