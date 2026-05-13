# Roadmap

This document describes the planned direction for `givp` over the next
twelve months. Items are subject to change based on user feedback and
available contributor time.

## Current version

**v1.0.0** - production release of the GRASP + ILS +
VND + Path Relinking metaheuristic for continuous, integer, and mixed
black-box optimization.
Available in **Python**, **Julia**, **Rust**, **C++** (header-only), and **R**.

## Short-term (next 3 months)

- **Rust literature comparison pipeline**: create
  `rust/benchmarks/run_literature_comparison.rs` with the same 6-function,
  30-seed protocol used in Python and Julia.
- **Docs architecture page**: add `docs/architecture.md` describing
  core modules (`grasp`, `vnd`, `ils`, `pr`, cache, elite, convergence)
  and the language-parity contract.
- **Benchmark chart automation**: publish reusable plots/tables in docs from
  the literature-comparison artifacts (Python, Julia, Rust, C++).
- **C++ package promotion**: track migration from staging overlays
  (`cpp/vcpkg_ports/arnime-givp/`, `cpp/conan/`) to upstream package indexes.
- **Expanded examples**: add worked examples for combinatorial objectives
  and multi-objective scalarization wrappers.

> **Recently completed (v1.0.0 line):**
> Julia package on General Registry (`Pkg.add("GIVPOptimizer")`),
> Rust `n_workers` with `rayon`, C++ literature comparison pipeline,
> C++ staging packaging (vcpkg/conan), Julia CLI, iteration callback,
> warm start, fuzzing drivers, and coverage/format quality gates.

## Medium-term (3–6 months)

- **Elite-pool warm start API**: allow callers to seed the elite pool with
  multiple known-good solutions (beyond a single `initial_guess`).
- **Configurable path-relinking strategies**: expose `forward`,
  `backward`, and randomized PR direction as an explicit option.
- **Documentation improvements**: add a dedicated Architecture page
  and benchmark comparison charts.

## Long-term (6–12 months)

- **Optional scikit-learn integration**: expose `givp` as a
  scikit-learn-compatible `BaseEstimator` for hyper-parameter tuning
  workflows.
- **Type-safe bounds specification**: accept named-parameter bounds via
  a mapping in addition to the current sequence-of-pairs format.
- **Async support**: explore asyncio-compatible runner for use in
  Jupyter and async frameworks.

## Out of scope

The following are explicitly out of scope for this project:

- **Gradient-based optimisation** — use SciPy or PyTorch for that.
- **Exact mathematical programming solvers** (MILP/MINLP) — dedicated tools
  such as OR-Tools, CBC, or commercial solvers are better suited.
- **GPU acceleration** — not currently planned.

## Feedback

If a feature you need is missing, please open a
[GitHub Issue](https://github.com/Arnime/grasp_ils_vnd_pr/issues) with the
label `enhancement`.
