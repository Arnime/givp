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

- **Expanded examples**:
  - [x] multi-objective scalarization wrapper example (Issue #141)
  - [x] combinatorial TSP-like discretized objective example (Issue #140)
- **Cross-port parameter semantics sync**:
  - [x] versioned parity checklist published (`docs/parameter-parity.md`)
    (Issue #138)
  - [x] docs synchronized to the canonical config contract across Python, Julia,
    Rust, C++, and R
- **Elite-pool warm start API — cross-port rollout** (Issue #142): completed
  across Python, Julia, Rust, C++, and R with multi-seed `initial_guesses`
  exposed in public APIs.
- **Configurable path-relinking strategies — cross-port rollout** (Issue #143):
  completed across Python, Julia, Rust, C++, and R with explicit
  `path_relink_strategy` (`bidirectional`, `forward`, `backward`,
  `randomized`; Python/Julia/R keep `random` alias compatibility).
- **Multilingual benchmark protocol parity for dissertation workflow**
  (Issue #172): completed protocol freeze for literature-comparison runners
  with aligned defaults (`n_runs=30`, `dims=10`, `max_iter=200`,
  `time_limit=30.0`, canonical baseline set), including R CLI `--time-limit`
  support and parity documentation updates.

> **Recently completed (v1.0.0 line):**
> Julia package on General Registry (`Pkg.add("GIVPOptimizer")`),
> Rust `n_workers` with `rayon`, C++ literature comparison pipeline,
> C++ staging packaging (vcpkg/conan), Julia CLI, iteration callback,
> warm start, fuzzing drivers, and coverage/format quality gates.
> Architecture page with Mermaid diagrams (`docs/architecture.md`) and
> navigation integration in MkDocs.
> Benchmark JSON schema v1 adopted by Python, Julia, Rust, and C++
> literature-comparison runners, with a shared documentation page.
> Rust literature comparison pipeline consolidated with canonical command,
> benchmark-runner location, schema v1 output, and smoke test coverage.
> Benchmark chart automation delivered through
> `python/benchmarks/publish_docs_artifacts.py`, which publishes generated
> benchmark report pages and reusable SVG charts in `docs/examples/` from the
> committed Python, Julia, Rust, C++, and R literature-comparison artifacts.
> Documentation improvements: benchmark comparison charts (`docs/examples/benchmark-reports/`),
> parity tables, and roadmap status synchronized with implemented changes.
> Optional scikit-learn integration (Issue #145): `GIVPOptimizer` now inherits
> from `sklearn.base.BaseEstimator` when scikit-learn is installed, enabling use
> in scikit-learn's `GridSearchCV`, `RandomizedSearchCV`, and other model
> selection / hyperparameter tuning pipelines via the `fit()` method.

## Medium-term (3–6 months)

- **C++ package promotion (from October 2026)**: track migration from staging
  overlays (`cpp/vcpkg_ports/arnime-givp/`, `cpp/conan/`) to upstream package
  indexes when the external submission window opens (Issue #139).

## Long-term (6–12 months)

- **Type-safe bounds specification** (Issue #146): accept named-parameter bounds
  via mapping in addition to the current sequence-of-pairs format.
- **Async support** (Issue #147): explore asyncio-compatible runner for use in
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
