# Julia

`givp` is also available as a native Julia package (`GIVPOptimizer.jl`),
providing the same GRASP-ILS-VND with Path Relinking algorithm with an idiomatic
Julia API.

## Installation

From a local clone of the repository:

```bash
cd julia
julia --project=. -e 'using Pkg; Pkg.instantiate()'
```

Requires Julia 1.9+.

## Quick start

```julia
using GIVPOptimizer

sphere(x) = sum(x .^ 2)

result = givp(sphere, [(-5.0, 5.0) for _ in 1:10])
println(result.x)       # best vector found
println(result.fun)     # best objective value
println(result.nfev)    # number of evaluations
```

## Maximize

```julia
result = givp(my_score, bounds; direction=maximize)
```

## Configuration

All the same hyper-parameters available in Python are exposed in Julia via
`GIVPConfig`:

```julia
cfg = GIVPConfig(;
    max_iterations=50,
    vnd_iterations=100,
    ils_iterations=10,
    elite_size=7,
    adaptive_alpha=true,
    time_limit=30.0,
)
result = givp(sphere, bounds; config=cfg, seed=42, verbose=true)
```

## Warm start

```julia
result = givp(
    rosenbrock,
    [(-2.0, 2.0) for _ in 1:5];
    initial_guess=[1.0, 1.0, 1.0, 1.0, 1.0],
)
```

## Mixed continuous/integer problems

```julia
n_cont, n_int = 12, 8
bounds = vcat(
    [(-5.0, 5.0) for _ in 1:n_cont],
    [(0.0, 4.0) for _ in 1:n_int],
)
cfg = GIVPConfig(; integer_split=n_cont)
result = givp(my_objective, bounds; config=cfg)
```

## Result struct

`givp` returns an `OptimizeResult` with the following fields:

| Field       | Type              | Meaning                                          |
|-------------|-------------------|--------------------------------------------------|
| `x`         | `Vector{Float64}` | Best solution vector.                            |
| `fun`       | `Float64`         | Objective value at `x` (user's original sign).   |
| `nit`       | `Int`             | GRASP outer iterations executed.                 |
| `nfev`      | `Int`             | Number of objective evaluations.                 |
| `success`   | `Bool`            | `true` when at least one feasible solution found.|
| `message`   | `String`          | Human-readable termination reason.               |
| `direction` | `Direction`       | `minimize` or `maximize`.                        |
| `meta`      | `Dict`            | Algorithm-specific extras.                       |

The result also supports `to_dict()` for JSON serialization.

## Running tests

```bash
cd julia
julia --project=. -e 'using Pkg; Pkg.test()'
```

With coverage:

```bash
julia --project=. -e 'using Pkg; Pkg.test(; coverage=true)'
```

## Experimental seed sweep API

For reproducible multi-seed studies, Julia also provides the same
`seed_sweep`/`sweep_summary` workflow as the Python port:

```julia
using GIVPOptimizer

sphere(x) = sum(x .^ 2)
bounds = [(-5.12, 5.12) for _ in 1:10]

rows = seed_sweep(sphere, bounds; seeds=0:29)
summary = sweep_summary(rows)

println(summary["fun"]["mean"])
println(summary["fun"]["std"])
```

Each row contains `seed`, `fun`, `nit`, `nfev`, `time_s`, `success`, and
`message`.

## CLI

A command-line interface equivalent to `givp run` is available at
`julia/cli.jl`:

```bash
# Inline lambda
julia julia/cli.jl run \
    --func '(x) -> sum(x .^ 2)' \
    --bounds '[[-5.0,-5.0,-5.0],[5.0,5.0,5.0]]' \
    --seed 42

# Load function from a source file
julia julia/cli.jl run \
    --func-file examples/sphere.jl --func-name sphere \
    --bounds '[[-5.12,-5.12],[5.12,5.12]]' --verbose

# JSON mode (mirrors Python CLI)
julia julia/cli.jl run --json '{"func_file":"sphere.jl","func_name":"sphere","bounds":[[-5],[5]]}'

julia julia/cli.jl version
```

Output is JSON to stdout — compatible with the Python `givp run` format.

## Literature comparison experiment

A reproducible multi-run experiment comparing GIVP against baselines is
provided in `julia/benchmarks/`:

```bash
# Run experiment: 30 seeds × 6 functions ×
# GIVP-full + DE + PSO + GA + CMA-ES + SA
julia --project=julia/benchmarks julia/benchmarks/run_literature_comparison.jl \
    --n-runs 30 --dims 10 --output results.json --verbose

# Include BlackBoxOptim.jl baselines (DE and XNES)
julia --project=julia/benchmarks julia/benchmarks/run_literature_comparison.jl \
    --algorithms GIVP-full BBO-DE BBO-XNES

# Generate Markdown + LaTeX tables with Wilcoxon tests
julia --project=julia/benchmarks julia/benchmarks/generate_report.jl \
    --input results.json --format both

# Include per-iteration convergence curves (requires --traces in run step)
julia --project=julia/benchmarks julia/benchmarks/run_literature_comparison.jl --traces
julia --project=julia/benchmarks julia/benchmarks/generate_report.jl \
    --input results.json --convergence
```

### Latest quick comparative snapshot (2026-05-18)

Command used:

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

An interactive version is available as a Jupyter notebook at
`Notebooks/Julia/benchmark_literature_comparison_julia.ipynb`.

## Running benchmarks

The benchmarks use `BenchmarkTools.jl` and cover four classic test functions
(sphere, rosenbrock, rastrigin, ackley) at dimensions 5 and 10:

```bash
cd julia
julia --project=. benchmarks/benchmarks.jl
```

Results are saved to `benchmarks/results.json` for regression tracking.
Subsequent runs automatically compare against the previous results.

## Fuzzing

A crash-finder fuzzer exercises the API with random and adversarial inputs:

```bash
julia --project=julia julia/fuzz/fuzz_givp.jl --n-trials 500 --verbose
```

Phase 1 checks that invalid inputs always raise the correct `GivpError` subtype.
Phase 2 runs random valid trials verifying six invariants per result
(bounds containment, `nfev > 0`, `success ↔ isfinite(fun)`, etc.).
Exit code 0 = all passed, 1 = failures found.

## Coverage

The CI enforces a minimum of **95 %** line coverage on `julia/src/`.
To check locally:

```bash
julia --project=julia -e '
  using Pkg; Pkg.add("CoverageTools")
  using CoverageTools
  cov = process_folder("julia/src")
  hit   = count(c -> c !== nothing && c > 0, [c for s in cov for c in s.coverage])
  total = count(c -> c !== nothing,          [c for s in cov for c in s.coverage])
  println("Coverage: $(round(hit/total*100; digits=1))%")
'
```

## API parity with Python

The Julia port aims for full feature parity with the Python implementation:

| Feature                    | Python | Julia |
|----------------------------|--------|-------|
| GRASP construction         | ✓      | ✓     |
| VND local search           | ✓      | ✓     |
| ILS perturbation           | ✓      | ✓     |
| Path Relinking             | ✓      | ✓     |
| Elite pool                 | ✓      | ✓     |
| Convergence monitor        | ✓      | ✓     |
| LRU evaluation cache       | ✓      | ✓     |
| Adaptive α                 | ✓      | ✓     |
| Time budget                | ✓      | ✓     |
| Mixed integer/continuous   | ✓      | ✓     |
| Warm start                 | ✓      | ✓     |
| Reproducible (`seed=`)     | ✓      | ✓     |
| CLI entry point            | ✓      | ✓     |
| `GIVPOptimizer` class      | ✓      | ✓     |
| Literature comparison      | ✓      | ✓     |
| Wilcoxon + LaTeX reports   | ✓      | ✓     |
| Fuzzing driver             | ✓      | ✓     |
