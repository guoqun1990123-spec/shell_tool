#!/usr/bin/env Rscript
# CLI wrapper: Rscript R/render_cli.R --config <path> --output <path>
# Must be run from the project root directory.

args <- commandArgs(trailingOnly = TRUE)

get_arg <- function(args, flag) {
  idx <- which(args == flag)
  if (length(idx) == 0 || idx >= length(args)) {
    stop(paste("Missing argument:", flag))
  }
  args[idx + 1]
}

config_file <- get_arg(args, "--config")
output_file <- get_arg(args, "--output")

source("R/generators/generate_shell.R")

generate_shell(
  config_file   = config_file,
  datasets_file = NULL,
  output_file   = output_file
)
