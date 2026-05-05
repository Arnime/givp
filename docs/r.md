<!-- SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior -->
<!-- SPDX-License-Identifier: MIT -->

# R

`givp` is available as an R package with a functional API (`givp`) and an
object-oriented API (`GIVPOptimizer`) based on R6.

## Installation

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
Rscript -e "testthat::test_dir('r/tests/testthat')"
```

## Literature Comparison Results (Notebook)

R benchmark results are currently tracked from
`Notebooks/R/benchmark_literature_comparison_r.ipynb` in two execution levels.

### Medium run

- Metadata: `n_runs=5`, `n_dims=10`
- Artifact: `Notebooks/R/benchmark_literature_comparison_r_results.json`

| Function | GIVP-full mean +- std | GRASP-only mean +- std | GIVP-full mean time (s) | GRASP-only mean time (s) |
|---|---|---|---|---|
| Sphere | 4.03e-02 +- 1.78e-02 | 2.691e+01 +- 7.1326e+00 | 8.8650 | 0.4568 |
| Rosenbrock | 3.0751e+01 +- 1.2204e+01 | 5.3734e+04 +- 2.2511e+04 | 13.3699 | 0.4136 |
| Rastrigin | 4.8871e+01 +- 6.7673e+00 | 8.5181e+01 +- 1.3954e+01 | 6.6203 | 0.4065 |
| Ackley | 3.7770e+00 +- 4.828e-01 | 1.9383e+01 +- 3.657e-01 | 8.9671 | 0.3784 |

### Robust run (checkpoint)

- Metadata: `n_runs=10`, `n_dims=10`, `max_iterations=80`,
  `vnd_iterations=150`, `ils_iterations=8`
- Artifact: `Notebooks/R/benchmark_literature_comparison_r_partial.csv`

| Function | GIVP-full mean +- std | GRASP-only mean +- std | GIVP-full mean time (s) | GRASP-only mean time (s) |
|---|---|---|---|---|
| Sphere | 2.1223e-02 +- 6.985e-03 | 2.3234e+01 +- 4.7093e+00 | 226.7211 | 1.0279 |
| Rosenbrock | 1.6037e+01 +- 3.6345e+00 | 3.1382e+04 +- 1.6223e+04 | 223.8017 | 0.9973 |
| Rastrigin | 3.6156e+01 +- 4.5694e+00 | 8.3601e+01 +- 1.0687e+01 | 162.9951 | 1.0632 |
| Ackley | 2.8140e+00 +- 3.4762e-01 | 1.8177e+01 +- 9.6254e-01 | 199.8611 | 1.3010 |

Checkpoint total runtime (observed):

- GIVP-full: `8123.83 s` (~2.26 h)
- GRASP-only: `43.90 s`
- Total: `8167.73 s` (~2.27 h)

These runs are suitable for development and release-note documentation.
For publication-level parity with other ports, prefer the full protocol
(`n_runs=30`).
