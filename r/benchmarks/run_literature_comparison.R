# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
#
# Reproducible multi-run literature comparison for the R GIVP port.
#
# Runs N independent seeds for 6 standard benchmark functions and two
# algorithm configurations (GIVP-full vs GRASP-only), then writes a
# JSON file compatible with python/benchmarks/generate_report.py.
#
# Usage (from repo root):
#   Rscript r/benchmarks/run_literature_comparison.R
#   Rscript r/benchmarks/run_literature_comparison.R \
#       --n-runs 30 --dims 10 --output results_r.json --verbose
#
# References:
#   De Jong (1975) — Sphere
#   Rosenbrock (1960) — Rosenbrock
#   Rastrigin (1974) — Rastrigin
#   Ackley (1987) — Ackley
#   Griewank (1981) — Griewank
#   Schwefel (1981) — Schwefel

# ── Bootstrap ──────────────────────────────────────────────────────────────────
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
  if (is.null(x) || (length(x) == 1L && is.na(x))) return("null")
  if (is.logical(x) && length(x) == 1L) return(if (x) "true" else "false")
  if (is.numeric(x) && length(x) == 1L) {
    if (is.infinite(x)) return(if (x > 0) "1e308" else "-1e308")
    if (is.nan(x)) return("null")
    return(sprintf("%.15g", x))
  }
  if (is.character(x) && length(x) == 1L) {
    return(paste0('"', gsub('"', '\\\\"', x), '"'))
  }
  if (is.numeric(x)) {
    vals <- vapply(x, to_json_value, character(1L))
    return(paste0("[", paste(vals, collapse = ", "), "]"))
  }
  if (is.list(x)) {
    if (!is.null(names(x))) {
      pairs <- mapply(
        function(k, v) paste0('"', k, '": ', to_json_value(v)),
        names(x), x, SIMPLIFY = FALSE
      )
      return(paste0("{", paste(unlist(pairs), collapse = ", "), "}"))
    }
    items <- lapply(x, to_json_value)
    return(paste0("[", paste(items, collapse = ", "), "]"))
  }
  to_json_value(as.character(x))
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
    output    = file.path("r", "benchmarks", "literature_comparison.json"),
    algorithms = c("GIVP-full", "GRASP-only"),
    verbose   = FALSE
  )
  i <- 1L
  while (i <= length(args)) {
    switch(args[[i]],
      "--n-runs"     = { params$n_runs    <- as.integer(args[[i + 1L]]); i <- i + 2L },
      "--dims"       = { params$dims      <- as.integer(args[[i + 1L]]); i <- i + 2L },
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
make_config_givp_full <- function(max_iter = 100L) {
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
    time_limit              = 0
  )
}

make_config_grasp_only <- function(max_iter = 100L) {
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
    time_limit              = 0
  )
}

ALGO_CONFIGS <- list(
  "GIVP-full"  = make_config_givp_full,
  "GRASP-only" = make_config_grasp_only
)

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
  if (!algo_name %in% names(ALGO_CONFIGS)) {
    warning(sprintf("Unknown algorithm '%s' — skipping", algo_name))
    next
  }
  cfg_fn <- ALGO_CONFIGS[[algo_name]]

  for (fn_name in FUNC_ORDER) {
    prob   <- PROBLEMS[[fn_name]]
    bounds <- prob$bounds_fn(DIMS)
    cfg    <- cfg_fn()

    fun_vals <- numeric(N_RUNS)
    nit_vals <- integer(N_RUNS)
    nfev_vals <- integer(N_RUNS)
    time_vals <- numeric(N_RUNS)

    for (run_i in seq_len(N_RUNS)) {
      seed <- run_i - 1L
      t0   <- proc.time()[[3L]]
      r    <- tryCatch(
        givp(prob$fn, bounds, direction = "minimize", config = cfg, seed = seed),
        error = function(e) {
          list(fun = Inf, nit = 0L, nfev = 0L, success = FALSE,
               message = conditionMessage(e))
        }
      )
      elapsed       <- proc.time()[[3L]] - t0
      fun_vals[[run_i]]  <- if (is.null(r$fun))  Inf else r$fun
      nit_vals[[run_i]]  <- if (is.null(r$nit))  0L  else r$nit
      nfev_vals[[run_i]] <- if (is.null(r$nfev)) 0L  else r$nfev
      time_vals[[run_i]] <- elapsed

      all_runs <- c(all_runs, list(list(
        algorithm  = algo_name,
        func       = fn_name,
        seed       = seed,
        fun        = fun_vals[[run_i]],
        nit        = nit_vals[[run_i]],
        nfev       = nfev_vals[[run_i]],
        time_s     = elapsed,
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
  for (algo_name in ALGORITHMS) {
    vals <- vapply(
      Filter(function(r) r$algorithm == algo_name && r$func == fn_name, all_runs),
      function(r) r$fun,
      numeric(1L)
    )
    algo_vals[[algo_name]] <- vals
    summary_rows <- c(summary_rows, list(list(
      func       = fn_name,
      algorithm  = algo_name,
      mean_val   = mean(vals),
      std_val    = sd(vals),
      best       = min(vals),
      median_val = median(vals),
      n          = N_RUNS,
      reference  = PROBLEMS[[fn_name]]$reference,
      optimum    = PROBLEMS[[fn_name]]$optimum
    )))
  }

  # Wilcoxon: compare each non-reference algo vs first algo
  if (length(ALGORITHMS) >= 2L) {
    ref_vals <- algo_vals[[ALGORITHMS[[1L]]]]
    for (algo_name in ALGORITHMS[-1L]) {
      chal_vals <- algo_vals[[algo_name]]
      wt <- wilcoxon_test(ref_vals, chal_vals)
      wilcoxon_rows <- c(wilcoxon_rows, list(list(
        func        = fn_name,
        reference   = ALGORITHMS[[1L]],
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
  meta = list(
    port            = "R",
    givp_version    = as.character(packageVersion("givp")),
    dims            = DIMS,
    n_runs          = N_RUNS,
    algorithms      = ALGORITHMS,
    functions       = FUNC_ORDER,
    timestamp       = format(Sys.time(), "%Y-%m-%dT%H:%M:%S")
  ),
  runs     = all_runs,
  summary  = summary_rows,
  wilcoxon = wilcoxon_rows
)

# Ensure output directory exists
out_dir <- dirname(OUTPUT)
if (!dir.exists(out_dir)) dir.create(out_dir, recursive = TRUE)

write_json(output_obj, OUTPUT)
cat(sprintf("\n[benchmark] Results saved to %s\n", OUTPUT))

# ── Console summary ────────────────────────────────────────────────────────────
cat("\n=== Summary (mean objective value) ===\n")
cat(sprintf("%-14s", "Function"))
for (algo in ALGORITHMS) cat(sprintf("  %-14s", algo))
cat("\n")
cat(strrep("-", 14L + 16L * length(ALGORITHMS)), "\n")

for (fn_name in FUNC_ORDER) {
  cat(sprintf("%-14s", fn_name))
  for (algo in ALGORITHMS) {
    row <- Filter(
      function(r) r$func == fn_name && r$algorithm == algo,
      summary_rows
    )[[1L]]
    cat(sprintf("  %14.4e", row$mean_val))
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
