# Language-neutral client for the synthetic hydropower worker.

library(jsonlite)
library(processx)

worker_command <- Sys.getenv(
  "SYNTHETIC_HYDROPOWER_COMMAND", "synthetic-hydropower"
)
arguments <- commandArgs(trailingOnly = TRUE)
request_path <- arguments[1]
response_path <- arguments[2]
if (is.na(request_path)) {
  stop("usage: Rscript client.R <batch-request.json> [response.json]")
}

request <- fromJSON(request_path, simplifyVector = FALSE)

is_windows_launcher <- function(command) {
  .Platform$OS.type == "windows" &&
    grepl("\\.cmd$", command, ignore.case = TRUE)
}

run_windows_batch <- function(
  command, input_path, destination_path = NA_character_
) {
  worker_script <- sub("\\.cmd$", "", command, ignore.case = TRUE)
  python_executable <- file.path(dirname(command), "python.exe")
  if (!file.exists(python_executable) || !file.exists(worker_script)) {
    stop("the Windows hydropower launcher is incomplete: ", command)
  }

  output_path <- tempfile("synthetic-hydropower-response-", fileext = ".json")
  on.exit(unlink(output_path), add = TRUE)
  result <- system2(
    python_executable,
    args = c(
      "-u", shQuote(worker_script), "balance", "--request", shQuote(input_path),
      "--output", shQuote(output_path)
    ),
    stdout = FALSE,
    stderr = TRUE
  )
  if (!identical(attr(result, "status"), NULL) &&
        attr(result, "status") != 0L) {
    stop(
      "the hydropower batch command failed: ",
      paste(result, collapse = "\n")
    )
  }
  if (!is.na(destination_path)) {
    dir.create(
      dirname(destination_path), recursive = TRUE, showWarnings = FALSE
    )
    if (!file.copy(output_path, destination_path, overwrite = TRUE)) {
      stop("unable to copy the hydropower response to: ", destination_path)
    }
    return(NULL)
  }
  fromJSON(output_path, simplifyVector = FALSE)
}

run_persistent_worker <- function(command, payload) {
  worker <- process$new(
    command, args = "worker", stdin = "|", stdout = "|", stderr = "|"
  )
  on.exit(worker$kill(), add = TRUE)
  worker$write_input(
    paste0(toJSON(payload, auto_unbox = TRUE, digits = NA), "\n")
  )
  io_status <- worker$poll_io(5000)
  if (io_status[["output"]] != "ready") {
    worker_error <- paste(worker$read_error_lines(), collapse = "\n")
    stop("the hydropower worker produced no response: ", worker_error)
  }
  fromJSON(worker$read_output_lines(n = 1), simplifyVector = FALSE)
}

response <- if (is_windows_launcher(worker_command)) {
  run_windows_batch(worker_command, request_path, response_path)
} else {
  run_persistent_worker(worker_command, request)
}

if (!is.null(response) && !is.null(response$error)) {
  stop(response$error$message)
}
if (!is.null(response) && !is.na(response_path)) {
  write_json(
    response, response_path, auto_unbox = TRUE, digits = NA, pretty = TRUE
  )
}
if (is.null(response)) {
  cat("wrote hydraulic response to", response_path, "\n")
} else {
  cat("received", length(response$results), "hydraulic result(s)\n")
  str(response$results[[1]]$simulation$level_m)
}
