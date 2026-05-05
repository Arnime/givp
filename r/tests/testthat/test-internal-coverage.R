# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT

ns_get <- function(name) {
  get(name, envir = asNamespace("givp"), inherits = FALSE)
}

make_eval_cache <- ns_get("make_eval_cache")
cache_get <- ns_get("cache_get")

evaluate_candidate <- ns_get("evaluate_candidate")
grasp_construct <- ns_get("grasp_construct")
vnd_search <- ns_get("vnd_search")
ils_search <- ns_get("ils_search")

path_relink_forward <- ns_get("path_relink_forward")
path_relink_backward <- ns_get("path_relink_backward")
path_relink_bidirectional <- ns_get("path_relink_bidirectional")
path_relink <- ns_get("path_relink")

make_result <- ns_get("make_result")
infer_termination_reason <- ns_get("infer_termination_reason")

simple_bounds <- function(n = 2L, low = -1, high = 1) {
  matrix(rep(c(low, high), n), ncol = 2, byrow = TRUE)
}

test_that("evaluate_candidate uses cache and updates nfev only on misses", {
  cache <- make_eval_cache(max_size = 8L)
  state <- new.env(parent = emptyenv())
  state$nfev <- 0L
  x <- c(0.25, -0.5)

  v1 <- evaluate_candidate(function(z) sum(z^2), x, cache, state)
  v2 <- evaluate_candidate(function(z) sum(z^2), x, cache, state)

  expect_equal(v1, v2)
  expect_equal(state$nfev, 1L)
  expect_equal(cache_get(cache, x), v1)
})

test_that("grasp_construct handles all-non-finite candidates with fallback", {
  cfg <- givp_config(num_candidates_per_step = 5L, integer_split = 1L)
  cache <- make_eval_cache(max_size = 16L)
  state <- new.env(parent = emptyenv())
  state$nfev <- 0L

  out <- grasp_construct(
    func = function(z) Inf,
    bounds = simple_bounds(3L),
    config = cfg,
    direction = "minimize",
    cache = cache,
    state = state
  )

  expect_true(all(is.finite(out$x)))
  expect_true(is.infinite(out$value))
  expect_equal(length(out$x), 3L)
})

test_that("vnd_search and ils_search keep candidates inside bounds", {
  cfg <- givp_config(
    vnd_iterations = 8L,
    ils_iterations = 3L,
    perturbation_strength = 2L,
    integer_split = 1L,
    seed = 123
  )
  cache <- make_eval_cache(max_size = 64L)
  state <- new.env(parent = emptyenv())
  state$nfev <- 0L

  b <- simple_bounds(2L, -2, 2)
  x0 <- c(1.5, -1.5)
  v0 <- evaluate_candidate(function(z) sum(z^2), x0, cache, state)

  vnd <- vnd_search(function(z) sum(z^2), x0, v0, b, cfg, "minimize", cache, state)
  ils <- ils_search(function(z) sum(z^2), x0, v0, b, cfg, "minimize", cache, state)

  expect_true(all(vnd$x >= b[, 1] & vnd$x <= b[, 2]))
  expect_true(all(ils$x >= b[, 1] & ils$x <= b[, 2]))
  expect_equal(vnd$x[2], round(vnd$x[2]))
  expect_equal(ils$x[2], round(ils$x[2]))
})

test_that("path relinking variants return finite objective on simple quadratic", {
  cfg <- givp_config(path_relink_frequency = 4L)
  cache <- make_eval_cache(max_size = 64L)
  state <- new.env(parent = emptyenv())
  state$nfev <- 0L

  b <- simple_bounds(2L, -3, 3)
  xa <- c(2, 2)
  xb <- c(-2, -2)
  fn <- function(z) sum(z^2)

  fwd <- path_relink_forward(fn, xa, xb, b, cfg, "minimize", cache, state)
  bwd <- path_relink_backward(fn, xa, xb, b, cfg, "minimize", cache, state)
  bi <- path_relink_bidirectional(fn, xa, xb, b, cfg, "minimize", cache, state)
  dispatch <- path_relink(fn, xa, xb, b, cfg, "minimize", cache, state)

  expect_true(is.finite(fwd$value))
  expect_true(is.finite(bwd$value))
  expect_true(is.finite(bi$value))
  expect_true(is.finite(dispatch$value))
})

test_that("termination reason inference covers all message branches", {
  expect_equal(infer_termination_reason("Convergence reached"), "converged")
  expect_equal(
    infer_termination_reason("Time limit reached"),
    "time_limit_reached"
  )
  expect_equal(
    infer_termination_reason("Early stop due to stagnation"),
    "early_stop"
  )
  expect_equal(infer_termination_reason("No feasible solution found"), "no_feasible")
  expect_equal(
    infer_termination_reason("Max iterations reached"),
    "max_iterations_reached"
  )
  expect_equal(infer_termination_reason("other status"), "unknown")
})

test_that("make_result assigns class and print method is stable", {
  res <- make_result(
    x = c(0, 0),
    fun = 0,
    nit = 3L,
    nfev = 10L,
    success = TRUE,
    message = "convergence reached",
    direction = "minimize"
  )

  expect_s3_class(res, "givp_result")
  expect_equal(res$termination, "converged")
  expect_output(print(res), "<givp_result>")
})

test_that("benchmark branches rosenbrock length<2 and rastrigin origin", {
  expect_equal(rosenbrock(c(1)), 0)
  expect_equal(rastrigin(c(0, 0, 0)), 0)
})
