# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
"""Reusable execution primitives for the synthetic-hydropower comparison."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from time import perf_counter

import numpy as np
from numpy.typing import NDArray

from benchmarks.comparison.hydropower.budget import SearchResult
from benchmarks.comparison.hydropower.de import run_de
from benchmarks.comparison.hydropower.givp import run_givp
from benchmarks.comparison.hydropower.pso import run_pso
from benchmarks.comparison.hydropower.upso import run_upso
from givp.examples.synthetic_hydropower.optimization import (
    OptimizationDefinition,
    evaluate_power_vector,
    project_power_vector,
    summarize_result,
)

ALGORITHMS = ("DE", "PSO", "UPSO", "GIVP")


@dataclass(frozen=True)
class OptimizerOutcome:
    """One canonical optimizer result before its physical JSON is persisted."""

    algorithm: str
    vector: NDArray[np.float64]
    objective: float
    optimizer_best_objective: float
    iterations: int
    evaluations: int
    elapsed_seconds: float
    termination: str
    physical_result: dict[str, object]
    diagnostics: dict[str, float]


def run_optimizer(
    algorithm: str,
    definition: OptimizationDefinition,
    profile: Mapping[str, object],
    seed: int | None = None,
) -> OptimizerOutcome:
    """Run one optimizer against the canonical objective.

    ``evaluations`` counts physical objective calls made by the optimizer. The
    returned vector is then projected and re-evaluated once as post-processing;
    that final evaluation is reported as ``objective`` and is not budgeted.
    """
    objective = _objective(definition)
    started = perf_counter()
    search = _search(algorithm, objective, definition, profile, seed)
    elapsed_seconds = perf_counter() - started
    if not search.termination:
        raise RuntimeError(f"{algorithm} finished without a termination reason")
    physical_objective, physical_result = evaluate_power_vector(
        search.vector, definition
    )
    if not np.isfinite(physical_objective):
        raise RuntimeError(f"{algorithm} returned a non-finite physical objective")
    return OptimizerOutcome(
        algorithm=algorithm,
        vector=project_power_vector(search.vector, definition).reshape(-1),
        objective=physical_objective,
        optimizer_best_objective=search.best_objective,
        iterations=search.iterations,
        evaluations=search.evaluations,
        elapsed_seconds=elapsed_seconds,
        termination=search.termination,
        physical_result=physical_result,
        diagnostics=summarize_result(physical_result),
    )


def zero_baseline(definition: OptimizationDefinition) -> dict[str, float]:
    """Return the canonical all-off objective decomposition for one scenario."""
    _, result = evaluate_power_vector(np.zeros(2 * definition.periods), definition)
    return summarize_result(result)


def _search(
    algorithm: str,
    objective: Callable[[NDArray[np.float64]], float],
    definition: OptimizationDefinition,
    profile: Mapping[str, object],
    seed: int | None,
) -> SearchResult:
    if algorithm == "DE":
        return run_de(objective, definition.bounds, profile, seed)
    if algorithm == "PSO":
        return run_pso(objective, definition.bounds, profile, seed)
    if algorithm == "UPSO":
        if profile.get("engine") == "pyswarm 0.6 pso":
            return run_pso(objective, definition.bounds, profile, seed)
        return run_upso(objective, definition.bounds, profile, seed)
    if algorithm == "GIVP":
        return run_givp(objective, definition, profile, seed)
    raise ValueError(f"unsupported synthetic-hydropower algorithm: {algorithm!r}")


def _objective(
    definition: OptimizationDefinition,
) -> Callable[[NDArray[np.float64]], float]:
    def evaluate(vector: NDArray[np.float64]) -> float:
        value, _ = evaluate_power_vector(vector, definition)
        return value

    return evaluate
