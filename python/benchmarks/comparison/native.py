# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
"""Adapter for native GIVP benchmark executions."""

from __future__ import annotations

from numpy.typing import NDArray

from benchmarks.common.models import Objective
from givp import GIVPConfig, givp


def run_givp(
    config: GIVPConfig,
    objective: Objective,
    bounds: list[tuple[float, float]],
    seed: int,
    capture_trace: bool,
) -> tuple[float, int, int, list[float] | None]:
    """Execute GIVP and optionally capture its best-so-far history."""
    history: list[float] | None = [] if capture_trace else None
    best = [float("inf")]

    def callback(iteration: int, cost: float, solution: NDArray) -> None:
        del iteration, solution
        best[0] = min(best[0], cost)
        if history is not None:
            history.append(best[0])

    result = givp(
        objective,
        bounds,
        config=config,
        seed=seed,
        iteration_callback=callback if capture_trace else None,
    )
    return float(result.fun), int(result.nit), int(result.nfev), history
