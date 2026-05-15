<!-- SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior -->
<!-- SPDX-License-Identifier: MIT -->

# Parameter Semantics Parity Checklist

This page versions the cross-port parameter checklist requested by Issue #138.
The canonical contract is the shared `GIVPConfig` surface used across Python,
Julia, Rust, C++, and R.

Audit date: 2026-05-15

## Scope

Checklist validates:

- parameter names and default values,
- value-range semantics,
- optimization direction semantics,
- docs synchronization status.

## Canonical parameter set

| Parameter | Python | Julia | Rust | C++ | R | Status |
|---|---|---|---|---|---|---|
| `max_iterations` | 100 | 100 | 100 | 100 | 100 | Aligned |
| `alpha` | 0.12 | 0.12 | 0.12 | 0.12 | 0.12 | Aligned |
| `vnd_iterations` | 200 | 200 | 200 | 200 | 200 | Aligned |
| `ils_iterations` | 10 | 10 | 10 | 10 | 10 | Aligned |
| `perturbation_strength` | 4 | 4 | 4 | 4 | 4 | Aligned |
| `use_elite_pool` | true | true | true | true | TRUE | Aligned |
| `elite_size` | 7 | 7 | 7 | 7 | 7 | Aligned |
| `path_relink_frequency` | 8 | 8 | 8 | 8 | 8 | Aligned |
| `path_relink_strategy` | bidirectional | bidirectional | Bidirectional | Bidirectional | bidirectional | Aligned |
| `adaptive_alpha` | true | true | true | true | TRUE | Aligned |
| `alpha_min` | 0.08 | 0.08 | 0.08 | 0.08 | 0.08 | Aligned |
| `alpha_max` | 0.18 | 0.18 | 0.18 | 0.18 | 0.18 | Aligned |
| `num_candidates_per_step` | 20 | 20 | 20 | 20 | 20 | Aligned |
| `use_cache` | true | true | true | true | TRUE | Aligned |
| `cache_size` | 10000 | 10000 | 10000 | 10000 | 10000 | Aligned |
| `early_stop_threshold` | 80 | 80 | 80 | 80 | 80 | Aligned |
| `use_convergence_monitor` | true | true | true | true | TRUE | Aligned |
| `n_workers` | 1 | 1 | 1 | 1 | 1 | Aligned |
| `time_limit` | 0.0 | 0.0 | 0.0 | 0.0 | 0 | Aligned |
| `direction` | minimize | minimize | Minimize | Minimize | minimize | Aligned |
| `integer_split` | None | nothing | None | nullopt | NULL | Aligned |
| `group_size` | None | nothing | None | nullopt | NULL | Aligned |

## Runtime-only parity

The following runtime fields are present in Rust/C++/R and exposed in language
specific APIs while remaining semantically equivalent to Python top-level API
arguments:

- `initial_guess`
- `seed`
- `verbose`

## Validation checklist

- [x] Parameter checklist is versioned in repository docs.
- [x] Default values are aligned for all shared config fields.
- [x] Range semantics are aligned (`alpha` in [0,1], positive iteration limits,
  etc.).
- [x] Direction semantics are aligned (`minimize` / `maximize`).
- [x] Documentation references added to roadmap.

## Evidence references

- Python: `python/src/givp/config.py`
- Julia: `julia/src/config.jl`
- Rust: `rust/src/config.rs`
- C++: `cpp/include/givp/config.hpp`
- R: `r/R/config.R`
