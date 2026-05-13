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
  - [x] versioned parity checklist published (`docs/parameter-parity.md`) (Issue #138)
  - [x] docs synchronized to the canonical config contract across Python, Julia, Rust, C++, and R

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

## Medium-term (3–6 months)

- **Elite-pool warm start API**: allow callers to seed the elite pool with
  multiple known-good solutions (beyond a single `initial_guess`).
- **Configurable path-relinking strategies**: expose `forward`,
  `backward`, and randomized PR direction as an explicit option.
- **Documentation improvements**: maintain benchmark comparison charts,
  parity tables, and roadmap status synchronized with implemented changes.
- **C++ package promotion (from October 2026)**: track migration from staging
  overlays (`cpp/vcpkg_ports/arnime-givp/`, `cpp/conan/`) to upstream package
  indexes when the external submission window opens.

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
