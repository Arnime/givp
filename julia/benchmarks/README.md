# Benchmark Results

## Performance benchmarks

Run the GIVPOptimizer micro-benchmarks with:

```bash
cd julia
julia --project=benchmarks -e 'using Pkg; Pkg.instantiate()'
julia --project=benchmarks benchmarks/benchmarks.jl
```

### Test functions

| Function   | Bounds        | Description                                |
|------------|---------------|--------------------------------------------|
| sphere     | [-5, 5]       | Sum of squares; minimum 0 at origin        |
| rosenbrock | [-2, 2]       | Banana function; minimum 0 at (1,…,1)      |
| rastrigin  | [-5.12, 5.12] | Highly multimodal; minimum 0 at origin     |
| ackley     | [-5, 5]       | Multimodal with flat regions; min 0 at 0   |

Each function is benchmarked at dimensions **5** and **10** (8 total cases).
Results are saved to `benchmarks/results.json`. Subsequent runs compare
against the previous results and flag regressions (>10% time increase).

---

## Literature comparison experiment

Reproducible multi-run experiment comparing GIVP against baselines on six
standard benchmark functions. Produces statistics and Wilcoxon-signed-rank
tables ready for SBPO / BRACIS papers.

### Latest quick snapshot (2026-05-18)

Executed in this repository with:

```bash
julia --project=julia/benchmarks julia/benchmarks/run_literature_comparison.jl \
    --n-runs 2 --dims 10 --max-iter 20 --time-limit 5 \
    --algorithms GIVP-full DE PSO GA CMA-ES SA \
    --output julia/benchmarks/reference_results_quick.json

julia --project=julia/benchmarks julia/benchmarks/generate_report.jl \
    --input julia/benchmarks/reference_results_quick.json --format both
```

Artifacts:

- `julia/benchmarks/reference_results_quick.json`
- `julia/benchmarks/reference_results_quick_report.md`
- `julia/benchmarks/reference_results_quick_report.tex`

Mean objective value (lower is better):

| Function | GIVP-full | DE | PSO | GA | CMA-ES | SA |
|---|---:|---:|---:|---:|---:|---:|
| Sphere | 3.0891e-04 | 8.9257e+00 | 3.3325e-01 | 3.4413e+01 | 1.4158e+01 | 6.6806e+01 |
| Rosenbrock | 9.7508e-01 | 1.3142e+04 | 3.6723e+02 | 1.1055e+05 | 1.0554e+05 | 7.6227e+05 |
| Rastrigin | 2.8570e+00 | 8.0447e+01 | 4.5557e+01 | 1.1610e+02 | 1.0374e+02 | 1.3776e+02 |
| Ackley | 2.8237e-01 | 1.6276e+01 | 7.0983e+00 | 1.9733e+01 | 2.0168e+01 | 2.0966e+01 |
| Griewank | 2.0511e-01 | 2.7312e+01 | 1.6317e+00 | 1.1915e+02 | 3.7558e+02 | 3.7715e+02 |
| Schwefel | 2.3860e+02 | 1.9453e+03 | 1.1423e+03 | 3.0391e+03 | 4.0803e+03 | 4.1722e+03 |

```bash
# 30 runs × 10-D × GIVP-full + DE + PSO + GA + CMA-ES + SA (all 6 functions)
julia --project=julia/benchmarks julia/benchmarks/run_literature_comparison.jl \
    --n-runs 30 --dims 10 --output results.json --verbose

# Include optional BlackBoxOptim.jl baselines as well
julia --project=julia/benchmarks julia/benchmarks/run_literature_comparison.jl \
    --algorithms GIVP-full DE PSO GA CMA-ES SA BBO-DE BBO-XNES

# Capture per-iteration convergence traces
julia --project=julia/benchmarks julia/benchmarks/run_literature_comparison.jl --traces

# Resume a partial run (checkpoint after every completed seed)
julia --project=julia/benchmarks julia/benchmarks/run_literature_comparison.jl --resume
```

### Generating reports

```bash
# Markdown + LaTeX tables with Wilcoxon tests (reads results.json)
julia --project=julia/benchmarks julia/benchmarks/generate_report.jl \
    --input results.json --format both

# With convergence curves (only if --traces was used above)
julia --project=julia/benchmarks julia/benchmarks/generate_report.jl \
    --input results.json --convergence --checkpoints 1 5 10 25 50 75 100
```

Outputs: `results_report.md` and `results_report.tex` in the same directory.

### Six benchmark functions

| Function   | Domain                     | Known optimum |
|------------|----------------------------|---------------|
| Sphere     | $[-5.12,\,5.12]^n$         | 0             |
| Rosenbrock | $[-5,\,10]^n$              | 0             |
| Rastrigin  | $[-5.12,\,5.12]^n$         | 0             |
| Ackley     | $[-32.768,\,32.768]^n$     | 0             |
| Griewank   | $[-600,\,600]^n$           | 0             |
| Schwefel   | $[-500,\,500]^n$           | 0             |

### Interactive notebook

`Notebooks/Julia/benchmark_literature_comparison_julia.ipynb` — run the full
experiment and generate all tables interactively in Jupyter.
