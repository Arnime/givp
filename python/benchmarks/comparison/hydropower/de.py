# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
"""Differential evolution exactly as the SOG ``DE`` wrapper invokes it.

SOG (``app/internal/modules/algoritmo/otimizacao/de.py``) calls
``scipy.optimize.differential_evolution`` with no seed, after a global
``np.random.seed``. The validated benchmark controls are ``popsize=20``,
``maxiter=100``, ``strategy='best1bin'``, ``mutation=(0.5, 1)``,
``recombination=0.9``, ``init='latinhypercube'``, ``updating='deferred'``,
``tol=0.09`` and ``polish=False``. See ``SOG_ALGORITHM_MAPPING.md``.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

import numpy as np
from numpy.typing import NDArray
from scipy.optimize import differential_evolution

from benchmarks.comparison.hydropower.budget import (
    CountingObjective,
    EvaluationBudgetExhaustedError,
    SearchResult,
    TimeLimitExceededError,
    boolean,
    integer,
    number,
    numbers,
    optional_integer,
    optional_number,
    seeded_global_numpy,
    string,
)


def run_de(
    objective: Callable[[NDArray[np.float64]], float],
    bounds: list[tuple[float, float]],
    profile: Mapping[str, object],
    seed: int | None,
) -> SearchResult:
    """Minimize ``objective`` with the SOG differential-evolution controls."""
    counted = CountingObjective(
        objective,
        optional_integer(profile, "max_evaluations"),
        optional_number(profile, "time_limit_seconds"),
    )
    workers = integer(profile, "execution_workers")
    if workers != 1:
        # SOG requested workers=-1; a process pool cannot share the evaluation
        # counter, so the budget would be silently unenforced.
        raise ValueError("DE execution_workers must be 1 to enforce the budget")
    generations = 0

    def count_generation(intermediate_result: Any) -> None:
        nonlocal generations
        generations += 1

    options: dict[str, Any] = {
        "strategy": string(profile, "strategy"),
        "maxiter": integer(profile, "max_iterations"),
        "popsize": integer(profile, "population_multiplier"),
        "tol": number(profile, "tolerance"),
        "mutation": tuple(numbers(profile, "mutation", 2)),
        "recombination": number(profile, "recombination"),
        "init": string(profile, "initialization"),
        "updating": str(profile.get("updating", "deferred")),
        "polish": boolean(profile, "polish"),
        "workers": workers,
        "callback": count_generation,
    }
    with seeded_global_numpy(seed):
        try:
            result = differential_evolution(counted, bounds, **options)
        except (EvaluationBudgetExhaustedError, TimeLimitExceededError) as error:
            vector, value = counted.best()
            return SearchResult(
                vector,
                value,
                generations,
                counted.evaluations,
                error.termination_reason,
            )
    return SearchResult(
        np.asarray(result.x, dtype=np.float64),
        float(result.fun),
        int(result.nit),
        counted.evaluations,
        _termination(str(result.message)),
    )


def _termination(message: str) -> str:
    lowered = message.lower()
    if "maximum number of iterations" in lowered:
        return "max_iterations"
    if "converged" in lowered:
        return "converged_tolerance"
    return message
