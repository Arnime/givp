# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT

ns_get <- function(name) {
  get(name, envir = asNamespace("givp"), inherits = FALSE)
}

normalize_bounds <- ns_get("normalize_bounds")
normalize_integer_tail <- ns_get("normalize_integer_tail")
set_seed_if_needed <- ns_get("set_seed_if_needed")
cache_get <- ns_get("cache_get")
cache_set <- ns_get("cache_set")
make_eval_cache <- ns_get("make_eval_cache")
path_relink_bidirectional <- ns_get("path_relink_bidirectional")

skip_if_not_full_profile()

# ── helpers.R: normalize_bounds matrix branch ─────────────────────────────────

test_that("normalize_bounds accepts a two-column matrix input", {
  b <- matrix(c(-1, 1, -2, 2), ncol = 2, byrow = TRUE)
  result <- normalize_bounds(b)
  expect_equal(nrow(result), 2L)
  expect_equal(result[1, 1], -1)
  expect_equal(result[2, 2], 2)
})

test_that("normalize_bounds rejects input that is neither list nor matrix", {
  expect_error(
    normalize_bounds(c(-1, 1, -2, 2)),
    class = "givp_error_invalid_bounds"
  )
})

# ── helpers.R: normalize_integer_tail half >= n branch ────────────────────────

test_that("normalize_integer_tail leaves x unchanged when integer_split >= n", {
  x <- c(1.1, 2.2, 3.3)
  expect_equal(normalize_integer_tail(x, integer_split = 3L), x)
  expect_equal(normalize_integer_tail(x, integer_split = 10L), x)
})

# ── helpers.R: set_seed_if_needed both-NULL no-op ─────────────────────────────

test_that("set_seed_if_needed with both NULL does not error", {
  expect_silent(set_seed_if_needed(NULL, NULL))
})

# ── cache.R: NULL cache short-circuits ────────────────────────────────────────

test_that("cache_get returns NULL when cache is NULL", {
  expect_null(cache_get(NULL, c(1, 2, 3)))
})

test_that("cache_set returns invisibly when cache is NULL", {
  expect_null(cache_set(NULL, c(1, 2, 3), 42))
})

# ── config.R: unknown field error ─────────────────────────────────────────────

test_that("GIVPConfig raises error for unknown field", {
  expect_error(
    GIVPConfig$new(totally_unknown_field = 99),
    class = "givp_error_invalid_config"
  )
})

# ── api.R: minimize = FALSE → maximize ───────────────────────────────────────

test_that("givp with minimize = FALSE resolves direction to maximize", {
  res <- givp(
    function(x) sum(x * x),
    bounds = list(c(-2, 2)),
    minimize = FALSE,
    seed = 1L
  )
  expect_equal(res$direction, "maximize")
})

# ── api.R: config not GIVPConfig → error ──────────────────────────────────────

test_that("givp raises error when config is not a GIVPConfig object", {
  expect_error(
    givp(
      function(x) sum(x * x),
      bounds = list(c(-1, 1)),
      config = list()
    ),
    class = "givp_error_invalid_config"
  )
})

# ── api.R: invalid direction string → error ───────────────────────────────────

test_that("givp raises error for invalid direction string", {
  expect_error(
    givp(
      function(x) sum(x * x),
      bounds = list(c(-1, 1)),
      direction = "sideways"
    ),
    class = "givp_error_invalid_config"
  )
})

# ── impl.R: initial_guess warm-start branch ───────────────────────────────────

test_that("givp with valid initial_guess uses warm-start path", {
  res <- givp(
    function(x) sum(x * x),
    bounds = list(c(-5, 5), c(-5, 5)),
    initial_guess = c(0.5, -0.5),
    seed = 42L
  )
  expect_s3_class(res, "givp_result")
  expect_true(is.finite(res$fun))
})

# ── impl.R: use_cache = FALSE ─────────────────────────────────────────────────

test_that("run_givp_native with use_cache = FALSE runs correctly", {
  cfg <- givp_config(
    max_iterations = 3L,
    vnd_iterations = 5L,
    ils_iterations = 2L,
    num_candidates_per_step = 5L,
    use_cache = FALSE
  )
  res <- givp(
    function(x) sum(x * x),
    bounds = list(c(-2, 2)),
    config = cfg,
    seed = 1L
  )
  expect_s3_class(res, "givp_result")
})

# ── impl.R: use_elite_pool = FALSE (no path relinking) ────────────────────────

test_that("run_givp_native with use_elite_pool = FALSE completes", {
  cfg <- givp_config(
    max_iterations = 4L,
    vnd_iterations = 5L,
    ils_iterations = 2L,
    num_candidates_per_step = 5L,
    use_elite_pool = FALSE
  )
  res <- givp(
    function(x) sum(x * x),
    bounds = list(c(-2, 2)),
    config = cfg,
    seed = 2L
  )
  expect_s3_class(res, "givp_result")
})

# ── impl.R: use_convergence_monitor = FALSE ───────────────────────────────────

test_that("run_givp_native with use_convergence_monitor = FALSE completes", {
  cfg <- givp_config(
    max_iterations = 4L,
    vnd_iterations = 5L,
    ils_iterations = 2L,
    num_candidates_per_step = 5L,
    use_convergence_monitor = FALSE
  )
  res <- givp(
    function(x) sum(x * x),
    bounds = list(c(-2, 2)),
    config = cfg,
    seed = 3L
  )
  expect_s3_class(res, "givp_result")
})

# ── impl.R: adaptive_alpha = FALSE (fixed alpha) ─────────────────────────────

test_that("run_givp_native with adaptive_alpha = FALSE uses constant alpha", {
  cfg <- givp_config(
    max_iterations = 3L,
    vnd_iterations = 5L,
    ils_iterations = 2L,
    num_candidates_per_step = 5L,
    adaptive_alpha = FALSE,
    alpha = 0.1
  )
  res <- givp(
    function(x) sum(x * x),
    bounds = list(c(-2, 2)),
    config = cfg,
    seed = 4L
  )
  expect_s3_class(res, "givp_result")
})

# ── impl.R: time_limit triggers early break ───────────────────────────────────

test_that("run_givp_native respects time_limit, reports time_limit_reached", {
  slow_fn <- function(x) {
    Sys.sleep(0.02)
    sum(x * x)
  }
  cfg <- givp_config(
    max_iterations = 1000L,
    vnd_iterations = 3L,
    ils_iterations = 1L,
    num_candidates_per_step = 3L,
    time_limit = 0.01
  )
  res <- givp(slow_fn, bounds = list(c(-1, 1)), config = cfg, seed = 5L)
  expect_equal(res$termination, "time_limit_reached")
})

# ── impl.R: all-Inf objective → success = FALSE, no_feasible ─────────────────

test_that("givp sets success=FALSE when objective always returns Inf", {
  cfg <- givp_config(
    max_iterations = 2L,
    vnd_iterations = 2L,
    ils_iterations = 1L,
    num_candidates_per_step = 3L
  )
  res <- givp(
    function(x) Inf,
    bounds = list(c(-1, 1), c(-1, 1)),
    config = cfg
  )
  expect_false(res$success)
  expect_equal(res$termination, "no_feasible")
})

# ── pr.R: path_relink_bidirectional backward-wins branch ─────────────────────

test_that("path_relink_bidirectional picks backward result when it is better", {
  cfg <- givp_config(path_relink_frequency = 4L)
  cache <- make_eval_cache(max_size = 64L)
  state <- new.env(parent = emptyenv())
  state$nfev <- 0L

  b <- matrix(c(-5, 5, -5, 5), ncol = 2, byrow = TRUE)
  # maximize -sum(x^2): passes through 0 going xb->xa,
  # yielding a better (less negative) value than xa alone.
  xa <- c(-4, -4)
  xb <- c(4, 4)
  fn <- function(z) -sum(z^2)

  bi <- path_relink_bidirectional(
    fn, xa, xb, b, cfg, "maximize", cache, state
  )
  expect_true(bi$value >= fn(xa))
})
