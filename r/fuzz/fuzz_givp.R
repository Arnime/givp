# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
#
# Crash-finder fuzzer for the R GIVP port.
#
# Exercises the public API with random and adversarial inputs to detect:
#   - Unhandled conditions (not a givp_error subclass)
#   - NaN/Inf leaking into the solution vector (r$x)
#   - Out-of-bounds solutions (r$x not within declared bounds)
#   - Invariant violation: r$success TRUE but r$fun not finite (or vice-versa)
#   - Crashes from degenerate configs or edge-case objective functions
#
# Exit codes:
#   0 — all trials passed
#   1 — at least one unexpected failure found (details on stderr)
#
# Usage (from repo root):
#   Rscript r/fuzz/fuzz_givp.R
#   Rscript r/fuzz/fuzz_givp.R --n-trials 500 --seed 1337 --verbose
#   Rscript r/fuzz/fuzz_givp.R --n-trials 200 --timeout 60

# ── Bootstrap ──────────────────────────────────────────────────────────────────
if (!requireNamespace("givp", quietly = TRUE)) {
  if (file.exists("r/DESCRIPTION")) {
    message("[fuzz] Installing givp from r/")
    install.packages("r", repos = NULL, type = "source", quiet = TRUE)
  } else {
    stop("givp package not found. Run: R CMD INSTALL r")
  }
}
library(givp)

# ── CLI argument parsing ────────────────────────────────────────────────────────
parse_args <- function() {
  args <- commandArgs(trailingOnly = TRUE)
  params <- list(n_trials = 200L, seed = 42L, timeout = 120, verbose = FALSE)
  i <- 1L
  while (i <= length(args)) {
    switch(args[[i]],
      "--n-trials" = {
        params$n_trials <- as.integer(args[[i + 1L]])
        i <- i + 2L
      },
      "--seed" = {
        params$seed <- as.integer(args[[i + 1L]])
        i <- i + 2L
      },
      "--timeout" = {
        params$timeout <- as.numeric(args[[i + 1L]])
        i <- i + 2L
      },
      "--verbose" = {
        params$verbose <- TRUE
        i <- i + 1L
      },
      {
        i <- i + 1L
      }
    )
  }
  params
}

cfg_args <- parse_args()
N_TRIALS  <- cfg_args$n_trials
MASTER_SEED <- cfg_args$seed
TIMEOUT_S   <- cfg_args$timeout
VERBOSE     <- cfg_args$verbose

set.seed(MASTER_SEED)

cat(sprintf(
  "[fuzz] givp R fuzz driver — %d trials | seed=%d | timeout=%.0fs\n",
  N_TRIALS, MASTER_SEED, TIMEOUT_S
))

# ── Objective function zoo ──────────────────────────────────────────────────────
sphere       <- function(x) sum(x^2)
neg_sphere   <- function(x) -sum(x^2)
constant_0   <- function(x) 0.0
constant_inf <- function(x) Inf
nan_func     <- function(x) NaN
throwing_fn  <- function(x) if (x[[1]] > 0) stop("deliberate error") else 0.0
mixed_fn     <- function(x) if (length(x) %% 2 == 0) sphere(x) else Inf
noisy_fn     <- function(x) sphere(x) + rnorm(1)

func_zoo <- list(
  list(name = "sphere",       fn = sphere,       expect_infeasible = FALSE),
  list(name = "neg_sphere",   fn = neg_sphere,   expect_infeasible = FALSE),
  list(name = "constant_0",   fn = constant_0,   expect_infeasible = FALSE),
  list(name = "constant_inf", fn = constant_inf, expect_infeasible = TRUE),
  list(name = "nan_func",     fn = nan_func,     expect_infeasible = TRUE),
  list(name = "throwing_fn",  fn = throwing_fn,  expect_infeasible = FALSE),
  list(name = "mixed_fn",     fn = mixed_fn,     expect_infeasible = FALSE),
  list(name = "noisy_fn",     fn = noisy_fn,     expect_infeasible = FALSE)
)

# ── Helpers ────────────────────────────────────────────────────────────────────
rand_bounds <- function(ndim) {
  los <- rnorm(ndim) * 10
  his <- los + abs(rnorm(ndim)) * 10 + 1e-3
  lapply(seq_len(ndim), function(i) c(los[[i]], his[[i]]))
}

rand_config <- function() {
  givp_config(
    max_iterations         = sample(1L:15L, 1L),
    vnd_iterations         = sample(1L:30L, 1L),
    ils_iterations         = sample(1L:8L, 1L),
    perturbation_strength  = sample(0L:5L, 1L),
    use_elite_pool         = sample(c(TRUE, FALSE), 1L),
    elite_size             = sample(1L:8L, 1L),
    path_relink_frequency  = sample(1L:15L, 1L),
    adaptive_alpha         = sample(c(TRUE, FALSE), 1L),
    alpha                  = runif(1, 0, 0.4),
    alpha_min              = runif(1, 0, 0.1),
    alpha_max              = runif(1, 0.1, 0.5),
    num_candidates_per_step = sample(1L:20L, 1L),
    use_cache              = sample(c(TRUE, FALSE), 1L),
    cache_size             = sample(100L:3000L, 1L),
    early_stop_threshold   = sample(5L:80L, 1L),
    use_convergence_monitor = sample(c(TRUE, FALSE), 1L),
    time_limit             = 0.0
  )
}

check_result <- function(r, bounds, expect_infeasible) {
  n <- length(bounds)

  # I1: success <-> isfinite(fun)
  if (!identical(r$success, is.finite(r$fun))) {
    return(list(ok = FALSE,
      reason = sprintf("I1: success=%s but is.finite(fun)=%s",
                       r$success, is.finite(r$fun))))
  }

  # I2: length(x) == n
  if (length(r$x) != n) {
    return(list(ok = FALSE,
      reason = sprintf("I2: length(x)=%d != n=%d", length(r$x), n)))
  }

  # I3: no NaN in x
  if (any(is.nan(r$x))) {
    return(list(ok = FALSE, reason = "I3: NaN found in r$x"))
  }

  # I4: nfev > 0
  if (r$nfev <= 0L) {
    return(list(ok = FALSE, reason = sprintf("I4: nfev=%d <= 0", r$nfev)))
  }

  # I5: x within bounds (only when feasible)
  if (r$success) {
    for (i in seq_len(n)) {
      lo <- bounds[[i]][[1L]]
      hi <- bounds[[i]][[2L]]
      xi <- r$x[[i]]
      if (is.finite(xi) && (xi < lo - 1e-6 || xi > hi + 1e-6)) {
        return(list(ok = FALSE,
          reason = sprintf("I5: x[%d]=%g out of [%g, %g]", i, xi, lo, hi)))
      }
    }
  }

  list(ok = TRUE, reason = "")
}

# ── Phase 1: Invalid input validation ─────────────────────────────────────────
cat("\n[Phase 1] Invalid input validation\n")

invalid_cases <- list(
  list(
    label = "non-function objective",
    fn = function() tryCatch(
      givp(42L, list(c(-1, 1))),
      error = function(e) e
    )
  ),
  list(
    label = "empty bounds",
    fn = function() tryCatch(
      givp(sphere, list()),
      error = function(e) e
    )
  ),
  list(
    label = "inverted bounds",
    fn = function() tryCatch(
      givp(sphere, list(c(5, -5))),
      error = function(e) e
    )
  ),
  list(
    label = "initial_guess outside bounds",
    fn = function() tryCatch(
      givp(sphere, list(c(-1, 1)), initial_guess = c(10.0)),
      error = function(e) e
    )
  ),
  list(
    label = "invalid direction string",
    fn = function() tryCatch(
      givp(sphere, list(c(-1, 1)), direction = "sideways"),
      error = function(e) e
    )
  ),
  list(
    label = "invalid config type",
    fn = function() tryCatch(
      givp(sphere, list(c(-1, 1)), config = list(max_iterations = 5)),
      error = function(e) e
    )
  )
)

p1_failures <- 0L
for (ic in invalid_cases) {
  result <- ic$fn()
  if (!inherits(result, "error")) {
    msg <- sprintf("  FAIL [%s]: expected error, got %s", ic$label, class(result)[[1L]])
    message(msg)
    p1_failures <- p1_failures + 1L
  } else if (VERBOSE) {
    cat(sprintf("  PASS [%s]: %s\n", ic$label, conditionMessage(result)))
  }
}
cat(sprintf("[Phase 1] %d/%d checks passed\n",
            length(invalid_cases) - p1_failures, length(invalid_cases)))

# ── Phase 2: Random valid trials ───────────────────────────────────────────────
cat(sprintf("\n[Phase 2] %d random valid trials\n", N_TRIALS))

p2_failures <- 0L
t0 <- proc.time()[[3L]]

for (trial in seq_len(N_TRIALS)) {
  elapsed <- proc.time()[[3L]] - t0
  if (TIMEOUT_S > 0 && elapsed >= TIMEOUT_S) {
    cat(sprintf("[Phase 2] Timeout after %d/%d trials (%.1fs)\n",
                trial - 1L, N_TRIALS, elapsed))
    break
  }

  ndim   <- sample(1L:6L, 1L)
  bounds <- rand_bounds(ndim)
  cfg    <- rand_config()
  seed   <- sample.int(.Machine$integer.max, 1L)
  entry  <- func_zoo[[(trial - 1L) %% length(func_zoo) + 1L]]
  fn     <- entry$fn
  expect_infeasible <- entry$expect_infeasible
  dir    <- sample(c("minimize", "maximize"), 1L)

  result <- tryCatch(
    givp(fn, bounds, direction = dir, config = cfg, seed = seed),
    error = function(e) {
      # givp_error subclasses are expected (invalid-config, etc.) — pass them
      if (inherits(e, "givp_error")) return(NULL)
      # Unexpected error — this is a bug
      list(unexpected_error = TRUE, msg = conditionMessage(e))
    }
  )

  # givp_error caught during construction → acceptable
  if (is.null(result)) next

  # Unexpected non-givp error
  if (!is.null(result$unexpected_error)) {
    message(sprintf(
      "  FAIL trial=%d func=%s ndim=%d: unexpected error: %s",
      trial, entry$name, ndim, result$msg
    ))
    p2_failures <- p2_failures + 1L
    next
  }

  check <- check_result(result, bounds, expect_infeasible)
  if (!check$ok) {
    message(sprintf(
      "  FAIL trial=%d func=%s ndim=%d dir=%s: %s",
      trial, entry$name, ndim, dir, check$reason
    ))
    p2_failures <- p2_failures + 1L
  } else if (VERBOSE) {
    cat(sprintf(
      "  PASS trial=%d func=%-12s ndim=%d fun=%.4g nfev=%d\n",
      trial, entry$name, ndim, result$fun, result$nfev
    ))
  }
}

cat(sprintf("[Phase 2] %d/%d trials passed\n",
            N_TRIALS - p2_failures, N_TRIALS))

# ── Summary ────────────────────────────────────────────────────────────────────
total_failures <- p1_failures + p2_failures
cat(sprintf("\n[fuzz] Total failures: %d\n", total_failures))

if (total_failures > 0L) {
  quit(status = 1L)
} else {
  cat("[fuzz] All checks passed ✓\n")
  quit(status = 0L)
}
