# Run the R GIVP against the persistent synthetic hydropower worker.

args <- commandArgs(trailingOnly = TRUE)
length(args) == 1L || stop("usage: Rscript optimize.R <optimization-definition.json>")

library(givp)
library(jsonlite)
script_argument <- commandArgs(trailingOnly = FALSE)
script_path <- sub("^--file=", "", script_argument[grepl("^--file=", script_argument)][[1L]])
source(file.path(dirname(normalizePath(script_path)), "adapter.R"))

definition <- jsonlite::fromJSON(args[[1L]], simplifyVector = FALSE)
worker <- new_hydropower_worker()
on.exit(close_hydropower_worker(worker), add = TRUE)

maximum <- unlist(definition$power_bounds_mw$maximum, use.names = FALSE)
bounds <- do.call(rbind, lapply(seq_len(2L), function(plant) {
  cbind(rep(0, definition$periods), rep(maximum[[plant]], definition$periods))
}))
baseline <- evaluate_hydropower(worker, rep(0, 48L), definition, "baseline")
config <- do.call(givp_config, definition$optimizer)
result <- givp(
  function(vector) hydropower_objective(worker, vector, definition),
  bounds = bounds,
  config = config,
  seed = definition$seed
)
physical <- evaluate_hydropower(worker, result$x, definition, "optimized")
cat(jsonlite::toJSON(list(
  language = "r",
  scenario = definition$scenario,
  baseline_objective = baseline$simulation$objective,
  optimizer_objective = result$fun,
  objective = physical$simulation$objective,
  energy_mwh = physical$simulation$energy_mwh,
  level_penalty = physical$simulation$level_penalty,
  power_deficit_mwh = sum(unlist(physical$power$power_deficit_mw)),
  target_power_mw = physical$power$target_power_mw
), auto_unbox = TRUE, digits = NA), "\n", sep = "")
