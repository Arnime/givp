"""Execution and statistical aggregation of reproducible seed sweeps."""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping, Sequence
from typing import Any

import numpy as np
import pandas as pd

from givp.api import givp
from givp.api.types import BoundsLike
from givp.config import GIVPConfig

SweepRow = Mapping[str, Any]
SweepResults = Sequence[SweepRow] | pd.DataFrame


def seed_sweep(
    func: Callable[[np.ndarray], float],
    bounds: BoundsLike,
    seeds: int | Sequence[int] = 30,
    *,
    config: GIVPConfig | None = None,
    direction: str = "minimize",
    verbose: bool = False,
) -> list[dict[str, Any]]:
    """Run independent optimizer executions and collect per-seed metrics."""
    seed_values = list(range(seeds)) if isinstance(seeds, int) else list(seeds)
    cfg = config if config is not None else GIVPConfig()
    rows: list[dict[str, Any]] = []
    for seed in seed_values:
        started_at = time.monotonic()
        result = givp(
            func,
            bounds,
            direction=direction,
            config=cfg,
            seed=seed,
            verbose=verbose,
        )
        rows.append(
            {
                "seed": seed,
                "fun": result.fun,
                "nit": result.nit,
                "nfev": result.nfev,
                "time_s": time.monotonic() - started_at,
                "success": result.success,
                "message": result.message,
            }
        )
    return rows


def _records_from_results(results: SweepResults) -> list[dict[str, Any]]:
    """Normalize sequence and DataFrame benchmark results into string-keyed rows."""
    if isinstance(results, pd.DataFrame):
        return [
            {str(key): value for key, value in record.items()}
            for record in results.to_dict(orient="records")
        ]
    return [dict(row) for row in results]


def sweep_summary(results: SweepResults) -> dict[str, dict[str, float]]:
    """Aggregate the numeric metrics from a multi-seed benchmark execution."""
    rows = _records_from_results(results)
    summary: dict[str, dict[str, float]] = {}
    for metric in ("fun", "nit", "nfev", "time_s"):
        values = np.asarray([float(row[metric]) for row in rows], dtype=float)
        summary[metric] = {
            "mean": float(np.mean(values)),
            "std": float(np.std(values, ddof=1)) if len(values) > 1 else 0.0,
            "min": float(np.min(values)),
            "max": float(np.max(values)),
        }
    return summary
