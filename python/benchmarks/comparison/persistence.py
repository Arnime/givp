# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
"""Result aggregation and checkpoint persistence."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np

import givp
from benchmarks.common.problems import ALGO_DESCRIPTIONS, PROBLEM_REGISTRY

_GIVP_VERSION = getattr(givp, "__version__", "unknown")
_log = logging.getLogger(__name__)


def _build_summary_rows(
    raw: dict[str, list[dict]],
    functions: list[str],
    algorithms: list[str],
) -> list[dict]:
    """Compute per-(function, algorithm) descriptive statistics from raw records."""
    summary: list[dict] = []
    for fn_name in functions:
        for algo in algorithms:
            values = [r["fun"] for r in raw[fn_name] if r["algorithm"] == algo]
            arr = np.asarray(values, dtype=float)
            nfev_arr = np.asarray(
                [r["nfev"] for r in raw[fn_name] if r["algorithm"] == algo],
                dtype=float,
            )
            summary.append(
                {
                    "function": fn_name,
                    "algorithm": algo,
                    "n_runs": len(values),
                    "mean": float(arr.mean()),
                    "std": float(arr.std(ddof=1)) if len(arr) > 1 else 0.0,
                    "best": float(arr.min()),
                    "median": float(np.median(arr)),
                    "worst": float(arr.max()),
                    "nfev_mean": float(nfev_arr.mean()),
                }
            )
    return summary


def _flatten_records(raw: dict[str, list[dict]], functions: list[str]) -> list[dict]:
    """Return records as a flat list in function order for schema v1 consumers."""
    runs: list[dict] = []
    for fn_name in functions:
        runs.extend(raw[fn_name])
    return runs


def _load_checkpoint(
    checkpoint_path: Path,
    raw: dict[str, list[dict]],
) -> tuple[set[str], int]:
    """Load completed function records from an existing checkpoint file.

    Returns (completed_functions, done_count).
    """
    completed: set[str] = set()
    done = 0
    ckpt = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    for fn_name, records in ckpt.get("records", {}).items():
        if fn_name in raw and records:
            raw[fn_name] = records
            completed.add(fn_name)
            done += len(records)
    if completed:
        _log.info("[resume] Skipping %s (already in checkpoint)", sorted(completed))
    return completed, done


def _save_checkpoint(
    checkpoint_path: Path,
    raw: dict[str, list[dict]],
    completed_functions: set[str],
    fn_name: str,
    algorithms: list[str],
    functions: list[str],
    dims: int,
    n_runs: int,
    seed_start: int,
    seeds: list[int],
    max_iter: int,
    time_limit: float,
) -> None:
    """Persist a partial checkpoint JSON after completing one function."""
    partial_summary = _build_summary_rows(
        raw, [fn for fn in functions if raw[fn]], algorithms
    )
    partial_payload = {
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
            "checkpoint": True,
            "completed_functions": sorted(completed_functions | {fn_name}),
            "problem_references": {
                fn: PROBLEM_REGISTRY[fn]["reference"] for fn in functions
            },
            "algo_descriptions": {a: ALGO_DESCRIPTIONS[a] for a in algorithms},
        },
        "runs": _flatten_records(raw, functions),
        "summary": partial_summary,
        "stats": partial_summary,
        "records": raw,
    }
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    checkpoint_path.write_text(json.dumps(partial_payload, indent=2), encoding="utf-8")
    _log.debug("  [checkpoint] saved after %s → %s", fn_name, checkpoint_path)
