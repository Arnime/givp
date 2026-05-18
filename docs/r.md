<!-- SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior -->
<!-- SPDX-License-Identifier: MIT -->

# R

`givp` is available as an R package with a functional API (`givp`) and an
object-oriented API (`GIVPOptimizer`) based on R6.

## Installation

From r-universe (recommended):

```r
install.packages(
  "givp",
  repos = c("https://arnime.r-universe.dev", "https://cloud.r-project.org")
)
```

Package page: <https://arnime.r-universe.dev/givp>

From a local clone:

```bash
R CMD INSTALL r
```

## Quick start

```r
library(givp)

sphere <- function(x) sum(x * x)
res <- givp(
  func = sphere,
  bounds = list(c(-5.12, 5.12), c(-5.12, 5.12)),
  seed = 42
)

print(res)
```

## Functional API

```r
givp(
  func,
  bounds,
  num_vars = NULL,
  minimize = NULL,
  direction = NULL,
  config = NULL,
  initial_guess = NULL,
  iteration_callback = NULL,
  seed = NULL,
  verbose = FALSE
)
```

## Configuration

```r
cfg <- givp_config(max_iterations = 50L, direction = "minimize")
res <- givp(sphere, bounds = list(c(-5, 5), c(-5, 5)), config = cfg)
```

## Object-oriented API

```r
opt <- GIVPOptimizer$new(
  func = sphere,
  bounds = list(c(-5, 5), c(-5, 5)),
  seed = 42
)
res <- opt$optimize()
```

## Error model

Errors follow an `rlang::abort()` hierarchy rooted at `givp_error`, with
specialized subclasses such as:

- `givp_error_invalid_bounds`
- `givp_error_invalid_config`
- `givp_error_invalid_initial_guess`
- `givp_error_invalid_objective`

## Testing

```bash
GIVP_R_TEST_PROFILE=quick Rscript -e "testthat::test_dir('r/tests/testthat')"
GIVP_R_TEST_PROFILE=full Rscript -e "testthat::test_dir('r/tests/testthat')"
```

- `quick`: skips long statistical quality-gate checks.
- `full`: runs the complete suite, including quality-gate checks.

## Parallel evaluation (`n_workers`)

The `n_workers` parameter controls how many worker processes evaluate
GRASP candidate solutions in parallel.

| Platform | Behaviour |
|---|---|
| Linux / macOS | Uses `parallel::mclapply`; `n_workers > 1` is fully supported |
| Windows | `mclapply` forks are not available; evaluation falls back silently to sequential (`n_workers = 1`) |

On Windows set `n_workers = 1L` explicitly to avoid confusion:

```r
cfg <- givp_config(n_workers = 1L)
res <- givp(sphere, bounds = list(c(-5, 5), c(-5, 5)), config = cfg)
```

This limitation is inherent to R's `parallel` package on Windows and cannot
be worked around without additional infrastructure (e.g. `doParallel` +
`foreach`). A future version may add Windows-compatible parallelism.

## Literature Comparison Results

The R port now supports CLI literature comparison with external baselines
(DE, PSO, GA, CMA-ES, SA) in `r/benchmarks/run_literature_comparison.R`.

### Latest quick comparative snapshot (2026-05-18)

Command used:

```bash
Rscript r/benchmarks/run_literature_comparison.R \
  --n-runs 2 --dims 10 --max-iter 20 \
  --algorithms GIVP-full DE PSO GA CMA-ES SA \
  --output r/benchmarks/reference_results_quick.json
python python/benchmarks/generate_report.py \
  --input r/benchmarks/reference_results_quick.json \
  --format both --output-dir r/benchmarks
```

Artifacts:

- `r/benchmarks/reference_results_quick.json`
- `r/benchmarks/reference_results_quick_report.md`
- `r/benchmarks/reference_results_quick_report.tex`
- `r/benchmarks/reference_results_quick_boxplot.png`

Mean objective value (lower is better):

| Function | GIVP-full | DE | PSO | GA | CMA-ES | SA |
|---|---:|---:|---:|---:|---:|---:|
| Sphere | 3.2618e-02 | 2.8878e+00 | 1.9852e+00 | 2.2568e-01 | 3.9992e+00 | 3.4896e+01 |
| Rosenbrock | 1.8084e+01 | 2.6546e+03 | 8.4086e+02 | 3.1931e+02 | 2.3069e+04 | 6.9496e+05 |
| Rastrigin | 4.1953e+01 | 4.5983e+01 | 5.5135e+01 | 2.0323e+01 | 8.8092e+01 | 1.3487e+02 |
| Ackley | 3.1125e+00 | 1.2169e+01 | 1.1900e+01 | 3.8547e+00 | 2.0482e+01 | 2.0804e+01 |
| Griewank | 1.0497e+00 | 1.0912e+01 | 7.8113e+00 | 2.4559e+00 | 2.9779e+02 | 3.2607e+02 |
| Schwefel | 1.0807e+03 | 1.6935e+03 | 2.3635e+03 | 1.9654e+03 | 2.1905e+03 | 2.7752e+03 |

For publication-level parity with other ports, prefer the full protocol
(`n_runs=30`) and fixed execution environments.
