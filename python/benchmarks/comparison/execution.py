# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
"""Literature comparison orchestration."""

from __future__ import annotations

import logging
from pathlib import Path

from benchmarks.common.problems import ALGO_DESCRIPTIONS, PROBLEM_REGISTRY
from benchmarks.comparison.algorithms import _run_single
from benchmarks.comparison.persistence import (
    _build_summary_rows,
    _flatten_records,
    _load_checkpoint,
    _save_checkpoint,
)
from givp import GIVPConfig, __version__

_GIVP_VERSION = __version__
_log = logging.getLogger(__name__)


def _run_function_seeds(
    fn_name: str,
    algorithms: list[str],
    seeds: list[int],
    dims: int,
    max_iter: int,
    time_limit: float,
    capture_traces: bool,
    givp_tuned_config: GIVPConfig | None,
    done_offset: int,
    total: int,
) -> tuple[list[dict], int]:
    """Run all (algo, seed) pairs for a single benchmark function.

    Returns (records, done_count) where done_count starts from *done_offset*.
    """
    spec = PROBLEM_REGISTRY[fn_name]
    bounds = spec["bounds_factory"](dims)
    func = spec["func"]
    records: list[dict] = []
    done = done_offset

    for algo in algorithms:
        for seed in seeds:
            rec = _run_single(
                algo,
                func,
                bounds,
                seed,
                max_iter,
                time_limit,
                capture_traces,
                givp_tuned_config=givp_tuned_config,
            )
            records.append(rec)
            done += 1
            trace_flag = " [+trace]" if rec["trace"] else ""
            _log.debug(
                "  [%4d/%d] %-12s %-12s seed=%3d  fun=%12.4e  nfev=%7d  t=%.2fs%s",
                done,
                total,
                fn_name,
                algo,
                seed,
                rec["fun"],
                rec["nfev"],
                rec["time_s"],
                trace_flag,
            )
    return records, done


def run_experiment(
    algorithms: list[str],
    functions: list[str],
    dims: int,
    n_runs: int,
    seed_start: int,
    max_iter: int,
    time_limit: float,
    capture_traces: bool,
    givp_tuned_config: GIVPConfig | None = None,
    checkpoint_path: Path | None = None,
    resume: bool = False,
) -> dict:
    """Run the full experiment matrix and return the result payload.

    Parameters
    ----------
    algorithms:
        Names from ALGO_DESCRIPTIONS to execute.
    functions:
        Names from PROBLEM_REGISTRY to benchmark.
    dims:
        Problem dimensionality (number of decision variables).
    n_runs:
        Number of independent runs per (algorithm, function) pair.
        Must be ≥ 2 for statistical tests; ≥ 30 recommended for publication.
    seed_start:
        First seed value; runs use seeds [seed_start, seed_start + n_runs).
    max_iter:
        Maximum GIVP iterations (or equivalent budget for scipy methods).
    time_limit:
        Per-run wall-clock budget in seconds.
    capture_traces:
        If True, store per-iteration best-value history (GIVP algorithms only).
        Increases output size significantly.
    givp_tuned_config:
        Pre-built GIVPConfig for the GIVP-tuned algorithm.  Required when
        ``"GIVP-tuned"`` is in *algorithms*.
    checkpoint_path:
        If set, the result JSON is written after each function completes,
        allowing ``--resume`` to skip already-finished functions.
    resume:
        If True and *checkpoint_path* exists, load previously completed
        function results and skip those functions.

    Returns
    -------
    dict
        Payload with keys: ``metadata``, ``summary``, ``records``.
    """
    seeds = list(range(seed_start, seed_start + n_runs))
    total = len(algorithms) * len(functions) * n_runs

    # --- resume: load already-computed function results from checkpoint ---
    raw: dict[str, list[dict]] = {fn: [] for fn in functions}
    completed_functions: set[str] = set()
    done = 0
    if resume and checkpoint_path is not None and checkpoint_path.exists():
        completed_functions, done = _load_checkpoint(checkpoint_path, raw)

    for fn_name in functions:
        if fn_name in completed_functions:
            continue

        fn_records, done = _run_function_seeds(
            fn_name,
            algorithms,
            seeds,
            dims,
            max_iter,
            time_limit,
            capture_traces,
            givp_tuned_config,
            done,
            total,
        )
        raw[fn_name] = fn_records

        # --- checkpoint: persist after each function ---
        if checkpoint_path is not None:
            _save_checkpoint(
                checkpoint_path,
                raw,
                completed_functions,
                fn_name,
                algorithms,
                functions,
                dims,
                n_runs,
                seed_start,
                seeds,
                max_iter,
                time_limit,
            )

    # Summary statistics (per function x algorithm)
    summary = _build_summary_rows(raw, functions, algorithms)

    return {
        "metadata": {
            "schema_version": "benchmark-schema-v1",
            "givp_version": _GIVP_VERSION,
            "dims": dims,
            "n_runs": n_runs,
            "seed_start": seed_start,
            "seeds": seeds,
            "max_iter": max_iter,
            "time_limit": time_limit,
            "algorithms": algorithms,
            "functions": functions,
            "problem_references": {
                fn: PROBLEM_REGISTRY[fn]["reference"] for fn in functions
            },
            "algo_descriptions": {a: ALGO_DESCRIPTIONS[a] for a in algorithms},
        },
        "runs": _flatten_records(raw, functions),
        "summary": summary,
        "stats": summary,
        "records": raw,
    }
