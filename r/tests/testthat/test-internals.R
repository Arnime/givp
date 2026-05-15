# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT

ns_get <- function(name) {
  get(name, envir = asNamespace("givp"), inherits = FALSE)
}

make_eval_cache <- ns_get("make_eval_cache")
cache_get <- ns_get("cache_get")
cache_set <- ns_get("cache_set")
cache_key <- ns_get("cache_key")

make_convergence_monitor <- ns_get("make_convergence_monitor")
convergence_update <- ns_get("convergence_update")

make_elite_pool <- ns_get("make_elite_pool")
elite_add <- ns_get("elite_add")
elite_best <- ns_get("elite_best")

normalize_bounds <- ns_get("normalize_bounds")
clamp_to_bounds <- ns_get("clamp_to_bounds")
normalize_integer_tail <- ns_get("normalize_integer_tail")
is_improvement <- ns_get("is_improvement")
better_value <- ns_get("better_value")
safe_eval <- ns_get("safe_eval")
set_seed_if_needed <- ns_get("set_seed_if_needed")

givp_abort <- ns_get("givp_abort")
abort_invalid_bounds <- ns_get("abort_invalid_bounds")
abort_invalid_config <- ns_get("abort_invalid_config")
abort_invalid_initial_guess <- ns_get("abort_invalid_initial_guess")
path_relink <- ns_get("path_relink")
path_relink_run <- ns_get(".path_relink_run")

seed_sweep <- ns_get("seed_sweep")
sweep_summary <- ns_get("sweep_summary")
sphere <- ns_get("sphere")
run_givp_native <- ns_get("run_givp_native")

test_that("cache implements get/set and LRU eviction", {
  cache <- make_eval_cache(max_size = 2L)

  x1 <- c(1, 2)
  x2 <- c(3, 4)
  x3 <- c(5, 6)

  expect_null(cache_get(cache, x1))

  cache_set(cache, x1, 10)
  cache_set(cache, x2, 20)
  expect_equal(cache_get(cache, x1), 10)
  expect_equal(cache_get(cache, x2), 20)

  cache_set(cache, x3, 30)
  expect_null(cache_get(cache, x1))
  expect_equal(cache_get(cache, x3), 30)
})

test_that("cache key is deterministic for same vector", {
  x <- c(0.123456, -9.9, 2)
  expect_identical(cache_key(x), cache_key(x))
})

test_that("convergence monitor updates for improvements and non-improvements", {
  monitor <- make_convergence_monitor()

  monitor <- convergence_update(monitor, 10, "minimize")
  expect_equal(monitor$no_improve, 0L)
  expect_equal(monitor$last_best, 10)

  monitor <- convergence_update(monitor, 12, "minimize")
  expect_equal(monitor$no_improve, 1L)
  expect_equal(monitor$last_best, 10)

  monitor <- convergence_update(monitor, 9, "minimize")
  expect_equal(monitor$no_improve, 0L)
  expect_equal(monitor$last_best, 9)
})

test_that("elite pool keeps best solutions for minimize and maximize", {
  min_pool <- make_elite_pool(max_size = 2L, direction = "minimize")
  min_pool <- elite_add(min_pool, c(0), 5)
  min_pool <- elite_add(min_pool, c(0), 2)
  min_pool <- elite_add(min_pool, c(0), 8)

  best_min <- elite_best(min_pool)
  expect_equal(best_min$value, 2)
  expect_length(min_pool$items, 2L)

  max_pool <- make_elite_pool(max_size = 2L, direction = "maximize")
  max_pool <- elite_add(max_pool, c(0), 5)
  max_pool <- elite_add(max_pool, c(0), 2)
  max_pool <- elite_add(max_pool, c(0), 8)

  best_max <- elite_best(max_pool)
  expect_equal(best_max$value, 8)
  expect_length(max_pool$items, 2L)
})

test_that("elite_best returns NULL for empty pool", {
  pool <- make_elite_pool(max_size = 2L)
  expect_null(elite_best(pool))
})

test_that("helpers normalize and clamp bounds correctly", {
  b_list <- list(c(-1, 1), c(0, 2))
  b <- normalize_bounds(b_list)
  expect_equal(nrow(b), 2L)
  expect_equal(ncol(b), 2L)

  clamped <- clamp_to_bounds(c(-5, 5), b)
  expect_equal(clamped, c(-1, 2))

  expect_error(
    normalize_bounds(list(c(-1, 1)), num_vars = 2L),
    class = "givp_error_invalid_bounds"
  )
})

test_that("integer tail normalization and comparison helpers work", {
  x <- c(1.1, 2.2, 3.3)
  expect_equal(normalize_integer_tail(x, integer_split = 1L), c(1.1, 2, 3))
  expect_equal(normalize_integer_tail(x, integer_split = NULL), x)

  expect_true(is_improvement(9, 10, "minimize"))
  expect_true(is_improvement(11, 10, "maximize"))

  expect_equal(better_value(1, 2, "minimize"), 1)
  expect_equal(better_value(1, 2, "maximize"), 2)
})

test_that("safe_eval handles finite, non-finite and error outputs", {
  expect_equal(safe_eval(function(z) sum(z), c(1, 2)), 3)
  expect_equal(safe_eval(function(z) Inf, c(1, 2)), Inf)
  expect_equal(safe_eval(function(z) stop("boom"), c(1, 2)), Inf)
})

test_that("set_seed_if_needed is deterministic for same seed", {
  set_seed_if_needed(seed = 123)
  a <- runif(3)
  set_seed_if_needed(seed = 123)
  b <- runif(3)
  expect_equal(a, b)

  set_seed_if_needed(seed = NULL, config_seed = 456)
  c <- runif(3)
  set_seed_if_needed(seed = NULL, config_seed = 456)
  d <- runif(3)
  expect_equal(c, d)
})

test_that("exception helpers raise the expected condition subclasses", {
  expect_error(givp_abort("x"), class = "givp_error")
  expect_error(abort_invalid_bounds("x"), class = "givp_error_invalid_bounds")
  expect_error(abort_invalid_config("x"), class = "givp_error_invalid_config")
  expect_error(
    abort_invalid_initial_guess("x"),
    class = "givp_error_invalid_initial_guess"
  )
})

test_that("seed_sweep and sweep_summary validate invalid inputs", {
  expect_error(
    seed_sweep(sphere, bounds = list(c(-1, 1)), n_runs = 0L),
    class = "givp_error_invalid_config"
  )

  expect_error(sweep_summary(list()), class = "givp_error_invalid_config")
})

test_that("run_givp_native supports single initial_guess fallback", {
  cfg <- givp_config(
    max_iterations = 3L,
    vnd_iterations = 6L,
    ils_iterations = 1L,
    num_candidates_per_step = 5L,
    seed = 7L,
    direction = "minimize"
  )
  cfg$initial_guess <- c(0.25, -0.25)
  cfg$initial_guesses <- NULL

  res <- run_givp_native(
    sphere,
    list(c(-1, 1), c(-1, 1)),
    cfg,
    "minimize",
    seed = 7L
  )

  expect_s3_class(res, "givp_result")
  expect_true(is.finite(res$fun))
})

test_that("path_relink supports all configured strategy modes", {
  quad <- function(x) sum(x * x)
  bounds <- normalize_bounds(list(c(-5, 5), c(-5, 5)))
  xa <- c(4, 4)
  xb <- c(-4, -4)

  for (strategy in c("bidirectional", "forward", "backward", "randomized")) {
    cfg <- givp_config(
      path_relink_frequency = 4L,
      path_relink_strategy = strategy
    )
    out <- path_relink(
      quad,
      xa,
      xb,
      bounds,
      cfg,
      "minimize",
      make_eval_cache(256L),
      new.env(parent = emptyenv())
    )
    expect_true(is.list(out))
    expect_true(all(c("x", "value") %in% names(out)))
    expect_true(is.finite(out$value))
  }
})

test_that("path_relink randomized mode covers both directions and invalid strategy", {
  quad <- function(x) sum(x * x)
  bounds <- normalize_bounds(list(c(-5, 5), c(-5, 5)))
  xa <- c(4, 4)
  xb <- c(-4, -4)
  cfg <- givp_config(path_relink_frequency = 4L)
  cache <- make_eval_cache(256L)
  state <- new.env(parent = emptyenv())

  set.seed(2)
  out_forward <- path_relink_run(
    "randomized",
    quad,
    xa,
    xb,
    bounds,
    cfg,
    "minimize",
    cache,
    state
  )

  set.seed(1)
  out_backward <- path_relink_run(
    "randomized",
    quad,
    xa,
    xb,
    bounds,
    cfg,
    "minimize",
    cache,
    state
  )

  expect_true(is.finite(out_forward$value))
  expect_true(is.finite(out_backward$value))

  expect_error(
    path_relink_run(
      "invalid",
      quad,
      xa,
      xb,
      bounds,
      cfg,
      "minimize",
      cache,
      state
    ),
    class = "givp_error_invalid_config"
  )
})
