# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
#
# Reproducible multi-run literature comparison for the R GIVP port.
#
# Runs N independent seeds for 6 standard benchmark functions and configurable
# algorithms (GIVP-full and/or external baselines), then writes a
# JSON file compatible with python/benchmarks/generate_report.py.
#
# Usage (from repo root):
#   Rscript r/benchmarks/run_literature_comparison.R
#   Rscript r/benchmarks/run_literature_comparison.R \
#       --n-runs 30 --dims 10 --max-iter 200 --time-limit 30 \
#       --algorithms GIVP-full DE PSO GA CMA-ES SA \
#       --output results_r.json --verbose
#
# References:
#   De Jong (1975) — Sphere
#   Rosenbrock (1960) — Rosenbrock
#   Rastrigin (1974) — Rastrigin
#   Ackley (1987) — Ackley
#   Griewank (1981) — Griewank
#   Schwefel (1981) — Schwefel

# ── Bootstrap ─────────────────────────────────────────────────────────────
if (!requireNamespace("givp", quietly = TRUE)) {
  if (file.exists("r/DESCRIPTION")) {
    message("[benchmark] Installing givp from r/")
    install.packages("r", repos = NULL, type = "source", quiet = TRUE)
  } else {
    stop("givp package not found. Run: R CMD INSTALL r")
  }
}
library(givp)

# ── JSON serialization (base R only, no external dep) ─────────────────────────
to_json_value <- function(x) {
  if (is.null(x)) return("null")
  if (is.data.frame(x)) {
    rows <- lapply(seq_len(nrow(x)), function(i) {
      row <- lapply(x[i, , drop = FALSE], function(v) v[[1L]])
      to_json_value(row)
    })
    return(paste0("[", paste(rows, collapse = ", "), "]"))
  }
  if (is.list(x)) {
    nms <- names(x)
    if (!is.null(nms) && length(nms) == length(x)) {
      pairs <- character(length(x))
      for (i in seq_along(x)) {
        pairs[[i]] <- paste0('"', nms[[i]], '": ', to_json_value(x[[i]]))
      }
      return(paste0("{", paste(pairs, collapse = ", "), "}"))
    }
    items <- character(length(x))
    for (i in seq_along(x)) items[[i]] <- to_json_value(x[[i]])
    return(paste0("[", paste(items, collapse = ", "), "]"))
  }
  if (length(x) == 0L) return("[]")
  if (length(x) > 1L) {
    items <- character(length(x))
    for (i in seq_along(x)) items[[i]] <- to_json_value(x[[i]])
    return(paste0("[", paste(items, collapse = ", "), "]"))
  }
  # scalar
  if (is.na(x)) return("null")
  if (is.logical(x)) return(if (x) "true" else "false")
  if (is.numeric(x)) {
    if (is.infinite(x)) return(if (x > 0) "1e308" else "-1e308")
    if (is.nan(x))      return("null")
    return(sprintf("%.15g", x))
  }
  # character / factor / anything else → coerce to string
  s <- as.character(x)[[1L]]
  paste0('"', gsub('\\\\', '\\\\\\\\', gsub('"', '\\\\"', s)), '"')
}

write_json <- function(obj, path) {
  writeLines(to_json_value(obj), path)
  invisible(path)
}

# ── CLI argument parsing ────────────────────────────────────────────────────────
parse_args <- function() {
  args <- commandArgs(trailingOnly = TRUE)
  params <- list(
    n_runs    = 30L,
    dims      = 10L,
    max_iter  = 200L,
    time_limit = 30.0,
    output    = file.path("r", "benchmarks", "literature_comparison.json"),
    algorithms = c("GIVP-full", "DE", "PSO", "GA", "CMA-ES", "SA"),
    verbose   = FALSE
  )
  i <- 1L
  while (i <= length(args)) {
    switch(args[[i]],
      "--n-runs"     = { params$n_runs    <- as.integer(args[[i + 1L]]); i <- i + 2L },
      "--dims"       = { params$dims      <- as.integer(args[[i + 1L]]); i <- i + 2L },
      "--max-iter"   = { params$max_iter  <- as.integer(args[[i + 1L]]); i <- i + 2L },
      "--time-limit" = { params$time_limit <- as.numeric(args[[i + 1L]]); i <- i + 2L },
      "--output"     = { params$output    <- args[[i + 1L]];             i <- i + 2L },
      "--algorithms" = {
        algs <- character(0L)
        j <- i + 1L
        while (j <= length(args) && !startsWith(args[[j]], "--")) {
          algs <- c(algs, args[[j]])
          j <- j + 1L
        }
        params$algorithms <- algs
        i <- j
      },
      "--verbose" = { params$verbose <- TRUE; i <- i + 1L },
      { i <- i + 1L }
    )
  }
  params
}

cli <- parse_args()
N_RUNS     <- cli$n_runs
DIMS       <- cli$dims
OUTPUT     <- cli$output
ALGORITHMS <- cli$algorithms
VERBOSE    <- cli$verbose
MAX_ITER   <- cli$max_iter
TIME_LIMIT <- cli$time_limit
ACTIVE_ALGORITHMS <- character(0L)

cat(sprintf(
  "[benchmark] R port | %d runs × %d-D × %s\n",
  N_RUNS, DIMS, paste(ALGORITHMS, collapse = " + ")
))

# ── Benchmark functions ────────────────────────────────────────────────────────
sphere <- function(x) sum(x^2)

rosenbrock <- function(x) {
  n <- length(x)
  if (n < 2L) return(0.0)
  sum(100.0 * (x[2L:n] - x[1L:(n - 1L)]^2)^2 + (1.0 - x[1L:(n - 1L)])^2)
}

rastrigin <- function(x) {
  10.0 * length(x) + sum(x^2 - 10.0 * cos(2 * pi * x))
}

ackley <- function(x) {
  n  <- length(x)
  sq <- sqrt(sum(x^2) / n)
  cs <- sum(cos(2 * pi * x)) / n
  -20.0 * exp(-0.2 * sq) - exp(cs) + 20.0 + exp(1.0)
}

griewank <- function(x) {
  1.0 + sum(x^2) / 4000.0 - prod(cos(x / sqrt(seq_along(x))))
}

schwefel <- function(x) {
  418.9829 * length(x) - sum(x * sin(sqrt(abs(x))))
}

# ── Problem registry ───────────────────────────────────────────────────────────
PROBLEMS <- list(
  Sphere = list(
    fn           = sphere,
    bounds_fn    = function(n) lapply(seq_len(n), function(...) c(-5.12, 5.12)),
    optimum      = 0.0,
    reference    = "De Jong (1975)"
  ),
  Rosenbrock = list(
    fn           = rosenbrock,
    bounds_fn    = function(n) lapply(seq_len(n), function(...) c(-5.0, 10.0)),
    optimum      = 0.0,
    reference    = "Rosenbrock (1960)"
  ),
  Rastrigin = list(
    fn           = rastrigin,
    bounds_fn    = function(n) lapply(seq_len(n), function(...) c(-5.12, 5.12)),
    optimum      = 0.0,
    reference    = "Rastrigin (1974)"
  ),
  Ackley = list(
    fn           = ackley,
    bounds_fn    = function(n) lapply(seq_len(n), function(...) c(-32.768, 32.768)),
    optimum      = 0.0,
    reference    = "Ackley (1987)"
  ),
  Griewank = list(
    fn           = griewank,
    bounds_fn    = function(n) lapply(seq_len(n), function(...) c(-600.0, 600.0)),
    optimum      = 0.0,
    reference    = "Griewank (1981)"
  ),
  Schwefel = list(
    fn           = schwefel,
    bounds_fn    = function(n) lapply(seq_len(n), function(...) c(-500.0, 500.0)),
    optimum      = 0.0,
    reference    = "Schwefel (1981)"
  )
)

FUNC_ORDER <- c("Sphere", "Rosenbrock", "Rastrigin", "Ackley", "Griewank", "Schwefel")

# ── Algorithm config builders ──────────────────────────────────────────────────
make_config_givp_full <- function(max_iter = 200L, time_limit = 30.0) {
  givp_config(
    max_iterations          = max_iter,
    alpha                   = 0.12,
    adaptive_alpha          = TRUE,
    alpha_min               = 0.08,
    alpha_max               = 0.18,
    vnd_iterations          = 200L,
    ils_iterations          = 10L,
    perturbation_strength   = 4L,
    use_elite_pool          = TRUE,
    elite_size              = 7L,
    path_relink_frequency   = 8L,
    use_cache               = TRUE,
    cache_size              = 10000L,
    early_stop_threshold    = 80L,
    use_convergence_monitor = TRUE,
    time_limit              = time_limit
  )
}

make_config_grasp_only <- function(max_iter = 200L, time_limit = 30.0) {
  givp_config(
    max_iterations          = max_iter,
    alpha                   = 0.12,
    adaptive_alpha          = FALSE,
    vnd_iterations          = 1L,
    ils_iterations          = 1L,
    perturbation_strength   = 0L,
    use_elite_pool          = FALSE,
    use_convergence_monitor = FALSE,
    use_cache               = TRUE,
    cache_size              = 10000L,
    early_stop_threshold    = max_iter,
    time_limit              = time_limit
  )
}

ALGO_CONFIGS <- list(
  "GIVP-full"  = make_config_givp_full,
  "GRASP-only" = make_config_grasp_only
)

ALGO_DESCRIPTIONS <- list(
  "GIVP-full"  = "GRASP-ILS-VND-PR -- full hybrid pipeline (this work)",
  "GRASP-only" = "GRASP-only baseline (Feo & Resende 1995)",
  "DE"         = "Differential Evolution -- DEoptim (Storn & Price 1997)",
  "PSO"        = "Particle Swarm Optimization -- pso::psoptim (Kennedy & Eberhart 1995)",
  "GA"         = "Genetic Algorithm -- GA package (Holland 1975)",
  "CMA-ES"     = "Covariance Matrix Adaptation Evolution Strategy -- cmaes package (Hansen & Ostermeier 2001)",
  "SA"         = "Simulated Annealing -- stats::optim(method='SANN') (Kirkpatrick et al. 1983)"
)

OPTIONAL_PACKAGES <- list(
  "DE" = "DEoptim",
  "PSO" = "pso",
  "GA" = "GA",
  "CMA-ES" = "cmaes"
)

is_algo_available <- function(algo_name) {
  pkg <- OPTIONAL_PACKAGES[[algo_name]]
  if (is.null(pkg)) return(TRUE)
  requireNamespace(pkg, quietly = TRUE)
}

bounds_to_vectors <- function(bounds) {
  list(
    lower = vapply(bounds, function(b) b[[1L]], numeric(1L)),
    upper = vapply(bounds, function(b) b[[2L]], numeric(1L))
  )
}

run_givp_baseline <- function(prob_fn, bounds, seed, max_iter, time_limit, cfg_fn) {
  cfg <- cfg_fn(max_iter, time_limit)
  t0 <- proc.time()[[3L]]
  r <- tryCatch(
    givp(prob_fn, bounds, direction = "minimize", config = cfg, seed = seed),
    error = function(e) {
      list(fun = Inf, nit = 0L, nfev = 0L, success = FALSE, message = conditionMessage(e))
    }
  )
  elapsed <- proc.time()[[3L]] - t0
  list(
    fun = if (is.null(r$fun)) Inf else r$fun,
    nit = if (is.null(r$nit)) 0L else r$nit,
    nfev = if (is.null(r$nfev)) 0L else r$nfev,
    time_s = elapsed,
    success = if (is.null(r$success)) FALSE else r$success
  )
}

run_de <- function(prob_fn, bounds, seed, max_iter) {
  bv <- bounds_to_vectors(bounds)
  eval_count <- 0L
  wrapped <- function(x) {
    eval_count <<- eval_count + 1L
    prob_fn(x)
  }
  set.seed(seed)
  t0 <- proc.time()[[3L]]
  out <- tryCatch({
    res <- DEoptim::DEoptim(
      fn = wrapped,
      lower = bv$lower,
      upper = bv$upper,
      control = DEoptim::DEoptim.control(itermax = max_iter, trace = FALSE)
    )
    list(fun = res$optim$bestval, nit = max_iter, nfev = eval_count, success = TRUE)
  }, error = function(e) {
    warning(sprintf("DE run failed (seed=%d): %s", seed, conditionMessage(e)))
    list(fun = Inf, nit = 0L, nfev = eval_count, success = FALSE)
  })
  out$time_s <- proc.time()[[3L]] - t0
  out
}

run_pso <- function(prob_fn, bounds, seed, max_iter) {
  bv <- bounds_to_vectors(bounds)
  eval_count <- 0L
  wrapped <- function(x) {
    eval_count <<- eval_count + 1L
    prob_fn(x)
  }
  set.seed(seed)
  x0 <- runif(length(bv$lower), min = bv$lower, max = bv$upper)
  t0 <- proc.time()[[3L]]
  out <- tryCatch({
    res <- pso::psoptim(
      par = x0,
      fn = wrapped,
      lower = bv$lower,
      upper = bv$upper,
      control = list(maxit = max_iter, trace = 0)
    )
    list(fun = res$value, nit = max_iter, nfev = eval_count, success = TRUE)
  }, error = function(e) {
    warning(sprintf("PSO run failed (seed=%d): %s", seed, conditionMessage(e)))
    list(fun = Inf, nit = 0L, nfev = eval_count, success = FALSE)
  })
  out$time_s <- proc.time()[[3L]] - t0
  out
}

run_ga <- function(prob_fn, bounds, seed, max_iter) {
  bv <- bounds_to_vectors(bounds)
  eval_count <- 0L
  fitness <- function(x) {
    eval_count <<- eval_count + 1L
    -prob_fn(x)
  }
  set.seed(seed)
  t0 <- proc.time()[[3L]]
  out <- tryCatch({
    ga_res <- GA::ga(
      type = "real-valued",
      fitness = fitness,
      lower = bv$lower,
      upper = bv$upper,
      popSize = max(20L, 10L * length(bv$lower)),
      maxiter = max_iter,
      run = max_iter,
      monitor = FALSE,
      seed = seed
    )
    list(fun = -ga_res@fitnessValue, nit = ga_res@iter, nfev = eval_count, success = TRUE)
  }, error = function(e) {
    warning(sprintf("GA run failed (seed=%d): %s", seed, conditionMessage(e)))
    list(fun = Inf, nit = 0L, nfev = eval_count, success = FALSE)
  })
  out$time_s <- proc.time()[[3L]] - t0
  out
}

run_cmaes <- function(prob_fn, bounds, seed, max_iter) {
  bv <- bounds_to_vectors(bounds)
  eval_count <- 0L
  wrapped <- function(x) {
    eval_count <<- eval_count + 1L
    prob_fn(x)
  }
  set.seed(seed)
  x0 <- runif(length(bv$lower), min = bv$lower, max = bv$upper)
  t0 <- proc.time()[[3L]]
  out <- tryCatch({
    cma_fun <- getExportedValue("cmaes", "cma_es")
    res <- cma_fun(
      par = x0,
      fn = wrapped,
      lower = bv$lower,
      upper = bv$upper,
      control = list(maxit = max_iter)
    )
    best_val <- if (!is.null(res$value)) res$value else wrapped(res$par)
    nit <- if (!is.null(res$iter)) as.integer(res$iter) else max_iter
    list(fun = best_val, nit = nit, nfev = eval_count, success = TRUE)
  }, error = function(e) {
    warning(sprintf("CMA-ES run failed (seed=%d): %s", seed, conditionMessage(e)))
    list(fun = Inf, nit = 0L, nfev = eval_count, success = FALSE)
  })
  out$time_s <- proc.time()[[3L]] - t0
  out
}

run_sa <- function(prob_fn, bounds, seed, max_iter) {
  bv <- bounds_to_vectors(bounds)
  eval_count <- 0L
  wrapped <- function(x) {
    eval_count <<- eval_count + 1L
    x_clipped <- pmin(pmax(x, bv$lower), bv$upper)
    penalty <- sum((x - x_clipped)^2) * 1e6
    prob_fn(x_clipped) + penalty
  }
  set.seed(seed)
  x0 <- runif(length(bv$lower), min = bv$lower, max = bv$upper)
  t0 <- proc.time()[[3L]]
  out <- tryCatch({
    res <- stats::optim(
      par = x0,
      fn = wrapped,
      method = "SANN",
      control = list(maxit = max_iter, trace = 0)
    )
    final_x <- pmin(pmax(res$par, bv$lower), bv$upper)
    list(fun = prob_fn(final_x), nit = max_iter, nfev = eval_count, success = TRUE)
  }, error = function(e) {
    warning(sprintf("SA run failed (seed=%d): %s", seed, conditionMessage(e)))
    list(fun = Inf, nit = 0L, nfev = eval_count, success = FALSE)
  })
  out$time_s <- proc.time()[[3L]] - t0
  out
}

run_external_baseline <- function(algo_name, prob_fn, bounds, seed, max_iter) {
  if (algo_name == "DE") return(run_de(prob_fn, bounds, seed, max_iter))
  if (algo_name == "PSO") return(run_pso(prob_fn, bounds, seed, max_iter))
  if (algo_name == "GA") return(run_ga(prob_fn, bounds, seed, max_iter))
  if (algo_name == "CMA-ES") return(run_cmaes(prob_fn, bounds, seed, max_iter))
  if (algo_name == "SA") return(run_sa(prob_fn, bounds, seed, max_iter))
  stop(sprintf("Unknown baseline algorithm: %s", algo_name))
}

# ── Wilcoxon signed-rank test (base R) ─────────────────────────────────────────
wilcoxon_test <- function(x, y, alpha = 0.05) {
  tryCatch({
    wt      <- wilcox.test(x, y, paired = TRUE, alternative = "less", exact = FALSE)
    n       <- length(x)
    r_stat  <- abs(2 * wt$statistic / (n * (n + 1L)) - 1)
    list(stat = wt$statistic, pvalue = wt$p.value,
         significant = wt$p.value < alpha, effect_r = r_stat)
  }, error = function(e) {
    list(stat = NA_real_, pvalue = 1.0, significant = FALSE, effect_r = 0.0)
  })
}

# ── Run experiment ──────────────────────────────────────────────────────────────
cat(sprintf("[benchmark] Running %d × %d × %d cells...\n",
            length(ALGORITHMS), length(FUNC_ORDER), N_RUNS))

all_runs <- list()

for (algo_name in ALGORITHMS) {
  if (!algo_name %in% names(ALGO_DESCRIPTIONS)) {
    warning(sprintf("Unknown algorithm '%s' — skipping", algo_name))
    next
  }
  if (!is_algo_available(algo_name)) {
    pkg <- OPTIONAL_PACKAGES[[algo_name]]
    warning(sprintf("Skipping %s: optional package '%s' is not installed", algo_name, pkg))
    next
  }

  ACTIVE_ALGORITHMS <- c(ACTIVE_ALGORITHMS, algo_name)

  cfg_fn <- ALGO_CONFIGS[[algo_name]]

  for (fn_name in FUNC_ORDER) {
    prob   <- PROBLEMS[[fn_name]]
    bounds <- prob$bounds_fn(DIMS)

    fun_vals <- numeric(N_RUNS)
    nit_vals <- integer(N_RUNS)
    nfev_vals <- integer(N_RUNS)
    time_vals <- numeric(N_RUNS)

    for (run_i in seq_len(N_RUNS)) {
      seed <- run_i - 1L
      r <- if (!is.null(cfg_fn)) {
        run_givp_baseline(prob$fn, bounds, seed, MAX_ITER, TIME_LIMIT, cfg_fn)
      } else {
        run_external_baseline(algo_name, prob$fn, bounds, seed, MAX_ITER)
      }
      fun_vals[[run_i]]  <- if (is.null(r$fun))  Inf else r$fun
      nit_vals[[run_i]]  <- if (is.null(r$nit))  0L  else r$nit
      nfev_vals[[run_i]] <- if (is.null(r$nfev)) 0L  else r$nfev
      time_vals[[run_i]] <- if (is.null(r$time_s)) 0 else r$time_s

      all_runs <- c(all_runs, list(list(
        algorithm  = algo_name,
        `function` = fn_name,
        seed       = seed,
        fun        = fun_vals[[run_i]],
        nit        = nit_vals[[run_i]],
        nfev       = nfev_vals[[run_i]],
        time_s     = time_vals[[run_i]],
        success    = if (is.null(r$success)) FALSE else r$success
      )))
    }

    mu   <- mean(fun_vals)
    best <- min(fun_vals)
    if (VERBOSE) {
      cat(sprintf("  %-12s × %-12s  mean=%.4e  best=%.4e  [%d runs]\n",
                  algo_name, fn_name, mu, best, N_RUNS))
    } else {
      cat(sprintf("  %-12s × %-12s done\n", algo_name, fn_name))
    }
  }
}

# ── Summary statistics ─────────────────────────────────────────────────────────
summary_rows <- list()
wilcoxon_rows <- list()

for (fn_name in FUNC_ORDER) {
  # collect per-algo vectors
  algo_vals <- list()
  for (algo_name in ACTIVE_ALGORITHMS) {
    vals <- vapply(
      Filter(function(r) r$algorithm == algo_name && r[["function"]] == fn_name, all_runs),
      function(r) r$fun,
      numeric(1L)
    )
    algo_vals[[algo_name]] <- vals
    nfev_vals <- vapply(
      Filter(function(r) r$algorithm == algo_name && r[["function"]] == fn_name, all_runs),
      function(r) r$nfev,
      numeric(1L)
    )
    mean_val <- if (length(vals) > 0L) mean(vals) else NaN
    std_val <- if (length(vals) > 1L) sd(vals) else 0.0
    best_val <- if (length(vals) > 0L) min(vals) else NaN
    median_val <- if (length(vals) > 0L) median(vals) else NaN
    worst_val <- if (length(vals) > 0L) max(vals) else NaN
    nfev_mean <- if (length(nfev_vals) > 0L) mean(nfev_vals) else NaN
    summary_rows <- c(summary_rows, list(list(
      `function` = fn_name,
      algorithm = algo_name,
      n_runs    = length(vals),
      mean      = mean_val,
      std       = std_val,
      best      = best_val,
      median    = median_val,
      worst     = worst_val,
      nfev_mean = nfev_mean
    )))
  }

  # Wilcoxon: compare each non-reference algo vs first algo
  if (length(ACTIVE_ALGORITHMS) >= 2L) {
    ref_vals <- algo_vals[[ACTIVE_ALGORITHMS[[1L]]]]
    for (algo_name in ACTIVE_ALGORITHMS[-1L]) {
      chal_vals <- algo_vals[[algo_name]]
      wt <- wilcoxon_test(ref_vals, chal_vals)
      wilcoxon_rows <- c(wilcoxon_rows, list(list(
        func        = fn_name,
        reference   = ACTIVE_ALGORITHMS[[1L]],
        challenger  = algo_name,
        stat        = wt$stat,
        pvalue      = wt$pvalue,
        significant = wt$significant,
        effect_r    = wt$effect_r
      )))
    }
  }
}

# ── Build output JSON ──────────────────────────────────────────────────────────
output_obj <- list(
  metadata = list(
    schema_version   = "benchmark-schema-v1",
    port             = "R",
    givp_version    = as.character(packageVersion("givp")),
    dims            = DIMS,
    n_runs          = N_RUNS,
    algorithms      = ACTIVE_ALGORITHMS,
    functions       = FUNC_ORDER,
    timestamp       = format(Sys.time(), "%Y-%m-%dT%H:%M:%S"),
    problem_references = lapply(PROBLEMS[FUNC_ORDER], function(p) p$reference),
    algo_descriptions = ALGO_DESCRIPTIONS[ACTIVE_ALGORITHMS]
  ),
  runs     = all_runs,
  records  = lapply(FUNC_ORDER, function(fn_name) {
    fn_rows <- Filter(function(r) r[["function"]] == fn_name, all_runs)
    lapply(fn_rows, function(r) {
      list(
        algorithm = r$algorithm,
        seed = r$seed,
        fun = r$fun,
        nit = r$nit,
        nfev = r$nfev,
        time_s = r$time_s,
        trace = NULL
      )
    })
  }),
  summary  = summary_rows,
  stats    = summary_rows,
  wilcoxon = wilcoxon_rows
)
names(output_obj$records) <- FUNC_ORDER

# Ensure output directory exists
out_dir <- dirname(OUTPUT)
if (!dir.exists(out_dir)) dir.create(out_dir, recursive = TRUE)

write_json(output_obj, OUTPUT)
cat(sprintf("\n[benchmark] Results saved to %s\n", OUTPUT))

# ── Console summary ────────────────────────────────────────────────────────────
cat("\n=== Summary (mean objective value) ===\n")
cat(sprintf("%-14s", "Function"))
for (algo in ACTIVE_ALGORITHMS) cat(sprintf("  %-14s", algo))
cat("\n")
cat(strrep("-", 14L + 16L * length(ACTIVE_ALGORITHMS)), "\n")

for (fn_name in FUNC_ORDER) {
  cat(sprintf("%-14s", fn_name))
  for (algo in ACTIVE_ALGORITHMS) {
    rows <- Filter(
      function(r) r[["function"]] == fn_name && r$algorithm == algo,
      summary_rows
    )
    if (length(rows) == 0L) {
      cat(sprintf("  %14s", "NA"))
    } else {
      cat(sprintf("  %14.4e", rows[[1L]]$mean))
    }
  }
  cat("\n")
}

if (length(wilcoxon_rows) > 0L) {
  cat("\n=== Wilcoxon signed-rank (one-sided, ref < challenger, p < 0.05) ===\n")
  for (w in wilcoxon_rows) {
    sig_marker <- if (isTRUE(w$significant)) "*" else " "
    cat(sprintf("  %-12s vs %-12s: p=%.4f  r=%.3f%s\n",
                w$reference, w$challenger, w$pvalue, w$effect_r, sig_marker))
  }
}

cat("\n[benchmark] Done.\n")
