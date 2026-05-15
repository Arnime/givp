# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT

#' Optimize with GIVP
#'
#' Functional entry point for the R port, mirroring the Python API.
#'
#' @param func Objective function receiving a numeric vector and
#'   returning scalar.
#' @param bounds Variable bounds.
#' @param num_vars Optional number of variables.
#' @param minimize Optional boolean for optimization direction.
#' @param direction Optional string (`"minimize"` or `"maximize"`).
#' @param config Optional `GIVPConfig` object.
#' @param initial_guess Optional warm-start vector.
#' @param initial_guesses Optional list of warm-start vectors.
#' @param iteration_callback Optional callback per iteration.
#' @param seed Optional RNG seed.
#' @param verbose Enable verbose output.
#' @return A `givp_result` object.
#' @export
#'
# nolint start: object_usage_linter
givp <- function(func,
                 bounds,
                 num_vars = NULL,
                 minimize = NULL,
                 direction = NULL,
                 config = NULL,
                 initial_guess = NULL,
                 initial_guesses = NULL,
                 iteration_callback = NULL,
                 seed = NULL,
                 verbose = FALSE) {
  if (!is.function(func)) {
    givp_abort("func must be a function", "givp_error_invalid_objective")
  }

  if (is.null(config)) {
    config <- givp_config()
  }
  if (!inherits(config, "GIVPConfig")) {
    givp_abort(
      "config must be a GIVPConfig object",
      "givp_error_invalid_config"
    )
  }

  resolved_direction <- config$direction
  if (!is.null(minimize)) {
    resolved_direction <- if (isTRUE(minimize)) "minimize" else "maximize"
  }
  if (!is.null(direction)) {
    resolved_direction <- direction
  }
  if (!resolved_direction %in% c("minimize", "maximize")) {
    givp_abort(
      "direction must be 'minimize' or 'maximize'",
      "givp_error_invalid_config"
    )
  }

  b <- normalize_bounds(bounds, num_vars)

  normalized_initial_guesses <- list()
  add_candidate <- function(candidate, label) {
    candidate_num <- as.numeric(candidate)
    if (length(candidate_num) != nrow(b)) {
      abort_invalid_initial_guess(
        paste0(label, " length does not match number of variables")
      )
    }
    if (any(candidate_num <= b[, 1] | candidate_num >= b[, 2])) {
      abort_invalid_initial_guess(
        paste0(label, " must be strictly inside bounds")
      )
    }
    duplicate <- any(vapply(normalized_initial_guesses, function(existing) {
      identical(existing, candidate_num)
    }, logical(1)))
    if (duplicate) {
      abort_invalid_initial_guess(
        paste0(label, " duplicates an existing warm-start candidate")
      )
    }
    normalized_initial_guesses[[length(normalized_initial_guesses) + 1L]] <<- candidate_num
  }

  if (!is.null(initial_guess)) {
    add_candidate(initial_guess, "initial_guess")
  }

  if (!is.null(initial_guesses)) {
    if (!is.list(initial_guesses)) {
      abort_invalid_initial_guess("initial_guesses must be a list of numeric vectors")
    }
    if (length(initial_guesses) == 0L) {
      abort_invalid_initial_guess(
        "initial_guesses must contain at least one candidate"
      )
    }
    for (idx in seq_along(initial_guesses)) {
      add_candidate(initial_guesses[[idx]], paste0("initial_guesses[", idx, "]"))
    }
  }

  if (length(normalized_initial_guesses) > 0L) {
    config$initial_guess <- normalized_initial_guesses[[1L]]
    config$initial_guesses <- normalized_initial_guesses
  } else {
    config$initial_guess <- NULL
    config$initial_guesses <- NULL
  }

  config$direction <- resolved_direction
  config$seed <- seed
  config$verbose <- isTRUE(verbose)

  result <- run_givp_native(func, b, config, resolved_direction, seed)

  if (is.function(iteration_callback)) {
    iteration_callback(result)
  }

  result
}
# nolint end

#' Object-oriented optimizer wrapper
#' @export
# nolint nextline object_name_linter
GIVPOptimizer <- R6::R6Class(
  "GIVPOptimizer",
  public = list(
    func = NULL,
    bounds = NULL,
    num_vars = NULL,
    minimize = NULL,
    direction = NULL,
    config = NULL,
    initial_guess = NULL,
    initial_guesses = NULL,
    iteration_callback = NULL,
    seed = NULL,
    verbose = FALSE,
    initialize = function(func,
                          bounds,
                          num_vars = NULL,
                          minimize = NULL,
                          direction = NULL,
                          config = NULL,
                          initial_guess = NULL,
                          initial_guesses = NULL,
                          iteration_callback = NULL,
                          seed = NULL,
                          verbose = FALSE) {
      self$func <- func
      self$bounds <- bounds
      self$num_vars <- num_vars
      self$minimize <- minimize
      self$direction <- direction
      self$config <- config
      self$initial_guess <- initial_guess
      self$initial_guesses <- initial_guesses
      self$iteration_callback <- iteration_callback
      self$seed <- seed
      self$verbose <- verbose
    },
    optimize = function() {
      givp(
        func = self$func,
        bounds = self$bounds,
        num_vars = self$num_vars,
        minimize = self$minimize,
        direction = self$direction,
        config = self$config,
        initial_guess = self$initial_guess,
        initial_guesses = self$initial_guesses,
        iteration_callback = self$iteration_callback,
        seed = self$seed,
        verbose = self$verbose
      )
    }
  )
)
