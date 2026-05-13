<!-- SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior -->
<!-- SPDX-License-Identifier: MIT -->

# Benchmark JSON schema v1

The literature-comparison runners for Python, Julia, Rust, and C++ now share a
common JSON envelope so downstream report generation can reason about a stable
contract.

## Required top-level keys

All benchmark artifacts must expose the following keys:

- `metadata`: experiment configuration and provenance.
- `runs`: flat list of individual trial records.
- `summary`: descriptive statistics grouped by `(function, algorithm)`.
- `stats`: alias of `summary` retained for tools that expect an explicit
  statistics section.

Some ports also keep legacy compatibility fields such as `records`.

## `metadata`

Required fields:

- `schema_version`: currently `benchmark-schema-v1`.
- `dims`: problem dimensionality.
- `n_runs`: independent runs per `(function, algorithm)` pair.
- `algorithms`: algorithm names included in the artifact.
- `functions`: benchmark functions included in the artifact.
- `problem_references`: mapping from function name to literature citation.
- `algo_descriptions`: mapping from algorithm name to a short description.

Ports may add extra provenance fields such as runtime version, package version,
seed ranges, timestamps, or checkpoint state.

## `runs`

Each entry in `runs` represents a single independent trial and should expose:

- `algorithm`
- `function`
- `seed`
- `fun`
- `nfev`
- `time_s`

Ports may include optional fields such as `nit` or convergence traces.

## `summary` and `stats`

Each entry in `summary` and `stats` is grouped by `(function, algorithm)` and
contains:

- `function`
- `algorithm`
- `n_runs`
- `mean`
- `std`
- `best`
- `median`
- `worst`
- `nfev_mean`

`stats` is intentionally duplicated from `summary` so older consumers can bind
against either name during the migration window.

## Compatibility notes

- Python keeps the historical `records` mapping by function in addition to the
  schema v1 fields.
- Julia keeps the historical flat `records` vector used by resume/report flows.
- Rust and C++ emit the schema v1 envelope directly.
