# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
"""Dispatch literature comparison runs to their owning adapters."""

from __future__ import annotations

import time

from benchmarks.common.models import Objective
from benchmarks.comparison.configs import (
    _config_givp_full,
    _config_givp_tuned,
    _config_grasp_only,
)
from benchmarks.comparison.native import run_givp
from benchmarks.comparison.pymoo import run_pymoo
from benchmarks.comparison.scipy import run_de, run_sa
from givp import GIVPConfig


def _givp_config(
    algorithm: str,
    max_iter: int,
    time_limit: float,
    tuned_config: GIVPConfig | None,
) -> GIVPConfig:
    """Build the configuration for a native GIVP comparison run."""
    if algorithm == "GIVP-full":
        return _config_givp_full(max_iter, time_limit)
    if algorithm == "GRASP-only":
        return _config_grasp_only(max_iter, time_limit)
    if tuned_config is None:
        raise RuntimeError(
            "GIVP-tuned requires --tune-config PATH (output of benchmarks.tuning).\n"
            "  python -m benchmarks.tuning --output best_config.json"
        )
    return _config_givp_tuned(tuned_config, max_iter, time_limit)


def _execute(
    algorithm: str,
    objective: Objective,
    bounds: list[tuple[float, float]],
    seed: int,
    max_iter: int,
    time_limit: float,
    capture_trace: bool,
    tuned_config: GIVPConfig | None,
) -> tuple[float, int, int, list[float] | None]:
    """Execute one algorithm through its dedicated adapter."""
    if algorithm in {"GIVP-full", "GRASP-only", "GIVP-tuned"}:
        config = _givp_config(algorithm, max_iter, time_limit, tuned_config)
        return run_givp(config, objective, bounds, seed, capture_trace)
    if algorithm == "DE":
        value, iterations, evaluations = run_de(objective, bounds, seed, max_iter)
    elif algorithm == "SA":
        value, iterations, evaluations = run_sa(objective, bounds, seed, max_iter)
    elif algorithm in {"PSO", "GA", "CMA-ES"}:
        value, iterations, evaluations = run_pymoo(
            algorithm, objective, bounds, seed, max_iter
        )
    else:
        raise ValueError(f"Unknown algorithm: {algorithm!r}")
    return value, iterations, evaluations, None


def _run_single(
    algo: str,
    func: Objective,
    bounds: list[tuple[float, float]],
    seed: int,
    max_iter: int,
    time_limit: float,
    capture_trace: bool,
    givp_tuned_config: GIVPConfig | None = None,
) -> dict[str, object]:
    """Execute one algorithm, objective and seed combination."""
    started_at = time.perf_counter()
    value, iterations, evaluations, trace = _execute(
        algo,
        func,
        bounds,
        seed,
        max_iter,
        time_limit,
        capture_trace,
        givp_tuned_config,
    )
    return {
        "algorithm": algo,
        "seed": seed,
        "fun": value,
        "nit": iterations,
        "nfev": evaluations,
        "time_s": round(time.perf_counter() - started_at, 4),
        "trace": trace,
    }
