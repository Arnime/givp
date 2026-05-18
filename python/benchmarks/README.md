# Benchmarks

This directory contains two kinds of benchmarks:

1. **Microbenchmarks** (`test_benchmarks.py`) — measure raw throughput with
   `pytest-benchmark`.  Excluded from the default test run.

2. **Scientific comparison scripts** — reproducible multi-run experiments
   against literature baselines with statistical significance tests.
   Suitable as supporting material for SBPO / BRACIS / journal submissions.

---

## 1. Microbenchmarks (pytest-benchmark)

```bash
cd python/
poetry install --with dev,benchmarks
poetry run pytest benchmarks/ --benchmark-only --benchmark-autosave
```

Results are stored under `.benchmarks/`.  Compare against a saved baseline:

```bash
poetry run pytest benchmarks/ --benchmark-compare=0001 --benchmark-only
```

---

## 2. Literature comparison (`run_literature_comparison.py`)

### Latest quick snapshot (2026-05-18)

Executed in this repository with:

```bash
cd python/
poetry run python benchmarks/run_literature_comparison.py \
    --dims 10 --n-runs 2 --max-iter 20 --time-limit 5 \
    --algorithms GIVP-full DE PSO GA CMA-ES SA \
    --output benchmarks/reference_results_quick.json

poetry run python benchmarks/generate_report.py \
    --input benchmarks/reference_results_quick.json \
    --format both --output-dir benchmarks/
```

Artifacts:

- `python/benchmarks/reference_results_quick.json`
- `python/benchmarks/reference_results_quick_report.md`
- `python/benchmarks/reference_results_quick_report.tex`
- `python/benchmarks/reference_results_quick_boxplot.png`

Mean objective value (lower is better):

| Function | GIVP-full | DE | PSO | GA | CMA-ES | SA |
|---|---:|---:|---:|---:|---:|---:|
| Sphere | 3.9947e-04 | 2.2680e-16 | 2.1758e-01 | 3.3073e-01 | 3.1402e+00 | 1.1483e-16 |
| Rosenbrock | 3.8670e+00 | 8.8226e-10 | 9.7634e+01 | 2.7370e+02 | 1.2180e+04 | 1.8086e-11 |
| Rastrigin | 4.0987e+00 | 1.9402e+01 | 3.1272e+01 | 1.0634e+01 | 1.1306e+02 | 7.1054e-15 |
| Ackley | 2.5727e-01 | 4.8165e+00 | 5.1259e+00 | 4.7871e+00 | 1.4550e+01 | 1.5884e-08 |
| Griewank | 3.0773e-01 | 5.1732e-02 | 1.7419e+00 | 2.4009e+00 | 2.0254e+01 | 1.1063e-02 |
| Schwefel | 1.0218e+03 | 1.1450e+03 | 1.9300e+03 | 2.7745e+02 | 2.2649e+03 | 1.2728e-04 |

### Quick start

```bash
cd python/
poetry install --with dev,benchmarks

# Default: 30 runs × 10-D × GIVP-full + DE + PSO + GA + CMA-ES + SA
poetry run python benchmarks/run_literature_comparison.py

# Explicit algorithm subset
poetry run python benchmarks/run_literature_comparison.py \
    --algorithms GIVP-full DE PSO GA CMA-ES SA

# Higher dimensionality, capture convergence traces
poetry run python benchmarks/run_literature_comparison.py \
    --dims 30 --n-runs 30 --traces \
    --output results_30d.json
```

### All options

```text
usage: run_literature_comparison [-h]
    [--dims N] [--n-runs N] [--seed-start N]
    [--max-iter N] [--time-limit SEC]
    [--algorithms ALGO [ALGO ...]]
    [--functions FUNC [FUNC ...]]
    [--output PATH] [--traces] [--verbose]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--dims` | 10 | Decision-variable count |
| `--n-runs` | 30 | Independent runs per cell (≥30 for publication) |
| `--seed-start` | 0 | First seed; uses `[N, N+n_runs)` |
| `--max-iter` | 200 | Max GIVP iterations (or equivalent budget) |
| `--time-limit` | 30.0 | Per-run wall-clock cap (seconds) |
| `--algorithms` | GIVP-full DE PSO GA CMA-ES SA | Any subset of `GIVP-full GIVP-tuned GRASP-only DE PSO GA CMA-ES SA` |
| `--functions` | all 6 | Any subset of `Sphere Rosenbrock Rastrigin Ackley Griewank Schwefel` |
| `--traces` | off | Capture per-iteration best-value history (GIVP only) |
| `--verbose` | off | Print one line per run |

---

## 3. Statistical report (`generate_report.py`)

Reads the JSON produced by `run_literature_comparison.py` and emits:

- Console summary table
- Wilcoxon signed-rank test results (α = 0.05)
- Markdown tables (paste into README or supplementary)
- LaTeX booktabs table (paste into SBPO / BRACIS paper)
- Boxplot PNG
- Convergence traces PNG (requires `--traces` in the experiment run)

### Quick start (Report)

```bash
# After running the experiment above:
poetry run python benchmarks/generate_report.py --input experiment_results.json

# LaTeX only, no plots
poetry run python benchmarks/generate_report.py \
    --input results_30d.json \
    --format latex --no-plots

# Save outputs to a paper directory
poetry run python benchmarks/generate_report.py \
    --input experiment_results.json \
    --output-dir paper/tables/
```

### All options (Benchmark)

```text
usage: generate_report [-h]
    --input PATH
    [--output-dir DIR]
    [--format {markdown,latex,both}]
    [--no-plots]
    [--reference ALGO]
    [--alpha FLOAT]
    [--trace-seed N]
```

---

## 4. Recommended workflow for paper submission

```bash
# Step 1 — run experiment (≈ 30 min on a laptop)
poetry run python benchmarks/run_literature_comparison.py \
    --dims 10 --n-runs 30 \
    --algorithms GIVP-full DE PSO GA CMA-ES SA \
    --traces --verbose \
    --output results/comparison_10d_30runs.json

# Step 2 — generate all outputs
poetry run python benchmarks/generate_report.py \
    --input results/comparison_10d_30runs.json \
    --format both \
    --output-dir paper/tables/

# Step 3 — include in paper
#   paper/tables/comparison_10d_30runs_report.tex  → \input{tables/...}
#   paper/tables/comparison_10d_30runs_boxplot.png → \includegraphics{...}
```

---

## 5. Benchmark functions

| Function | Domain | Global optimum | Reference |
|----------|--------|----------------|-----------|
| Sphere | `[-5.12, 5.12]^n` | 0 at **0** | De Jong (1975) |
| Rosenbrock | `[-5, 10]^n` | 0 at **1** | Rosenbrock (1960) |
| Rastrigin | `[-5.12, 5.12]^n` | 0 at **0** | Rastrigin (1974) |
| Ackley | `[-32.768, 32.768]^n` | 0 at **0** | Ackley (1987) |
| Griewank | `[-600, 600]^n` | 0 at **0** | Griewank (1981) |
| Schwefel | `[-500, 500]^n` | ≈0 at ≈420.97 | Schwefel (1981) |

All implemented in `givp.benchmarks`; global minima confirmed in the literature.
