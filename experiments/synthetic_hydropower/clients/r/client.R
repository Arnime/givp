# Language-neutral client for the synthetic hydropower worker.

library(jsonlite)
library(processx)

worker_command <- Sys.getenv("SYNTHETIC_HYDROPOWER_COMMAND", "synthetic-hydropower")
request_path <- commandArgs(trailingOnly = TRUE)[1]
if (is.na(request_path)) {
  stop("usage: Rscript client.R <batch-request.json>")
}

request <- fromJSON(request_path, simplifyVector = FALSE)

is_windows_launcher <- function(command) {
  .Platform$OS.type == "windows" && grepl("\\.cmd$", command, ignore.case = TRUE)
}

run_windows_batch <- function(command, input_path) {
  worker_script <- sub("\\.cmd$", "", command, ignore.case = TRUE)
  python_executable <- file.path(dirname(command), "python.exe")
  if (!file.exists(python_executable) || !file.exists(worker_script)) {
    stop("the Windows hydropower launcher is incomplete: ", command)
  }

  output_path <- tempfile("synthetic-hydropower-response-", fileext = ".json")
  on.exit(unlink(output_path), add = TRUE)
  result <- processx::run(
    python_executable,
    args = c("-u", worker_script, "balance", "--request", input_path, "--output", output_path),
    error_on_status = FALSE
  )
  if (result$status != 0L) {
    stop("the hydropower batch command failed: ", result$stderr)
  }
  fromJSON(output_path, simplifyVector = FALSE)
}

run_persistent_worker <- function(command, payload) {
  worker <- process$new(command, args = "worker", stdin = "|", stdout = "|", stderr = "|")
  on.exit(worker$kill(), add = TRUE)
  worker$write_input(paste0(toJSON(payload, auto_unbox = TRUE, digits = NA), "\n"))
  io_status <- worker$poll_io(5000)
  if (io_status[["output"]] != "ready") {
    worker_error <- paste(worker$read_error_lines(), collapse = "\n")
    stop("the hydropower worker produced no response: ", worker_error)
  }
  fromJSON(worker$read_output_lines(n = 1), simplifyVector = FALSE)
}

response <- if (is_windows_launcher(worker_command)) {
  run_windows_batch(worker_command, request_path)
} else {
  run_persistent_worker(worker_command, request)
}

if (!is.null(response$error)) {
  stop(response$error$message)
}
cat("received", length(response$results), "hydraulic result(s)\n")
str(response$results[[1]]$simulation$level_m)
