# Reusable persistent-worker adapter for synthetic hydropower optimisation.

new_hydropower_worker <- function(command = Sys.getenv(
  "SYNTHETIC_HYDROPOWER_COMMAND",
  "synthetic-hydropower"
)) {
  if (.Platform$OS.type == "windows" && grepl("\\.cmd$", command, ignore.case = TRUE)) {
    python <- file.path(dirname(command), "python.exe")
    script <- sub("\\.cmd$", "", command, ignore.case = TRUE)
    if (!file.exists(python) || !file.exists(script)) {
      stop("the Windows hydropower launcher is incomplete: ", command)
    }
    return(processx::process$new(
      python, args = c("-u", script, "worker"), stdin = "|", stdout = "|", stderr = "|"
    ))
  }
  processx::process$new(command, args = "worker", stdin = "|", stdout = "|", stderr = "|")
}

close_hydropower_worker <- function(worker) {
  if (worker$is_alive()) worker$kill()
  invisible(NULL)
}

project_power <- function(vector, definition) {
  values <- matrix(as.numeric(vector), nrow = 2L, byrow = TRUE)
  minimum <- as.numeric(definition$power_bounds_mw$minimum)
  maximum <- as.numeric(definition$power_bounds_mw$maximum)
  for (plant in seq_len(2L)) {
    values[plant, ] <- pmin(pmax(values[plant, ], 0), maximum[plant])
    values[plant, values[plant, ] < minimum[plant] / 2] <- 0
    values[plant, values[plant, ] > 0 & values[plant, ] < minimum[plant]] <- minimum[plant]
  }
  values
}

evaluate_hydropower <- function(worker, vector, definition, case_id = "candidate") {
  schedule <- project_power(vector, definition)
  payload <- list(
    schema_version = "synthetic-hydropower/v1",
    requests = list(list(
      case_id = case_id,
      incremental_inflow_m3s = definition$incremental_inflow_m3s,
      target_power_mw = unname(split(schedule, row(schedule)))
    ))
  )
  worker$write_input(paste0(jsonlite::toJSON(payload, auto_unbox = TRUE, digits = NA), "\n"))
  status <- worker$poll_io(30000)
  if (status[["output"]] != "ready") {
    stop("hydropower worker did not return a response")
  }
  response <- jsonlite::fromJSON(worker$read_output_lines(n = 1L), simplifyVector = FALSE)
  if (!is.null(response$error)) stop(response$error$message)
  response$results[[1L]]
}

hydropower_objective <- function(worker, vector, definition) {
  result <- evaluate_hydropower(worker, vector, definition)
  value <- result$simulation$objective
  if (!is.numeric(value) || length(value) != 1L || !is.finite(value)) {
    stop("hydropower response has no finite canonical objective")
  }
  value
}
