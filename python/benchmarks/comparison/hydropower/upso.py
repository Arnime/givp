# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
"""Unified PSO using the initialization and stopping conventions of pyswarm 0.6."""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping

import numpy as np
from numpy.typing import NDArray

from benchmarks.comparison.hydropower.budget import (
    CountingObjective,
    EvaluationBudgetExhaustedError,
    SearchResult,
    TimeLimitExceededError,
    integer,
    number,
    optional_integer,
    optional_number,
    seeded_global_numpy,
)

_MINSTEP = 1e-8
_MINFUNC = 1e-8


def run_upso(
    objective: Callable[[NDArray[np.float64]], float],
    bounds: list[tuple[float, float]],
    profile: Mapping[str, object],
    seed: int | None,
) -> SearchResult:
    """Run a ring/global unified swarm with pyswarm-compatible mechanics.

    The global and local PSO velocity proposals are blended by
    ``unification_factor``. Initial positions and velocities, asynchronous
    best updates, bound clipping, and native convergence checks follow
    ``pyswarm.pso`` 0.6.
    """
    counted = CountingObjective(
        objective,
        optional_integer(profile, "max_evaluations"),
        optional_number(profile, "time_limit_seconds"),
    )
    swarm_size = integer(profile, "population_size")
    max_generations = integer(profile, "max_generations")
    neighborhood_size = integer(profile, "neighborhood_size")
    unification_factor = number(profile, "unification_factor")
    c1 = number(profile, "c1")
    c2 = number(profile, "c2")
    w_min = number(profile, "w_min")
    w_max = number(profile, "w_max")
    if swarm_size < 1:
        raise ValueError("population_size must be positive")
    if max_generations < 0:
        raise ValueError("max_generations must be non-negative")
    if neighborhood_size < 3 or neighborhood_size % 2 == 0:
        raise ValueError("neighborhood_size must be an odd integer of at least three")
    if not math.isfinite(unification_factor) or not 0.0 <= unification_factor <= 1.0:
        raise ValueError("unification_factor must be finite and between zero and one")
    if not all(math.isfinite(value) for value in (c1, c2, w_min, w_max)):
        raise ValueError("UPSO coefficients and inertia weights must be finite")
    if c1 < 0.0 or c2 < 0.0:
        raise ValueError("acceleration coefficients must be non-negative")
    if w_min < 0.0 or w_max < w_min:
        raise ValueError("inertia weights must satisfy zero <= w_min <= w_max")

    limits = np.asarray(bounds, dtype=np.float64)
    if (
        limits.ndim != 2
        or limits.shape[1] != 2
        or limits.shape[0] == 0
        or not np.all(np.isfinite(limits))
        or np.any(limits[:, 1] <= limits[:, 0])
    ):
        raise ValueError(
            "bounds must contain finite lower/upper pairs with lower < upper"
        )

    lower = limits[:, 0]
    upper = limits[:, 1]
    velocity_high = np.abs(upper - lower)
    velocity_low = -velocity_high
    dimension = len(lower)
    positions = np.empty((swarm_size, dimension), dtype=np.float64)
    velocities = np.zeros_like(positions)
    personal_best_positions = np.zeros_like(positions)
    personal_best_values = np.full(swarm_size, float("inf"), dtype=np.float64)
    global_best_position = np.zeros(dimension, dtype=np.float64)
    global_best_value = float("inf")
    offsets = np.arange(
        -(neighborhood_size // 2), neighborhood_size // 2 + 1, dtype=np.intp
    )
    termination = "max_iterations"
    iterations = 0

    with seeded_global_numpy(seed):
        try:
            positions[:] = lower + np.random.rand(swarm_size, dimension) * (
                upper - lower
            )
            for index in range(swarm_size):
                personal_best_positions[index] = positions[index]
                personal_best_values[index] = counted(personal_best_positions[index])
                if index == 0:
                    global_best_position = personal_best_positions[index].copy()
                if personal_best_values[index] < global_best_value:
                    global_best_value = personal_best_values[index]
                    global_best_position = personal_best_positions[index].copy()
                velocities[index] = velocity_low + np.random.rand(dimension) * (
                    velocity_high - velocity_low
                )

            for iteration in range(1, max_generations + 1):
                iterations = iteration
                progress = (iteration - 1) / max(max_generations - 1, 1)
                omega = w_max - (w_max - w_min) * progress
                personal_random = np.random.uniform(size=(swarm_size, dimension))
                global_random = np.random.uniform(size=(swarm_size, dimension))
                local_random = np.random.uniform(size=(swarm_size, dimension))

                for index in range(swarm_size):
                    neighbors = (index + offsets) % swarm_size
                    local_index = neighbors[np.argmin(personal_best_values[neighbors])]
                    personal_delta = personal_best_positions[index] - positions[index]
                    global_velocity = (
                        omega * velocities[index]
                        + c1 * personal_random[index] * personal_delta
                        + c2
                        * global_random[index]
                        * (global_best_position - positions[index])
                    )
                    local_velocity = (
                        omega * velocities[index]
                        + c1 * personal_random[index] * personal_delta
                        + c2
                        * local_random[index]
                        * (personal_best_positions[local_index] - positions[index])
                    )
                    velocities[index] = (
                        unification_factor * global_velocity
                        + (1.0 - unification_factor) * local_velocity
                    )
                    positions[index] = np.clip(
                        positions[index] + velocities[index], lower, upper
                    )
                    value = counted(positions[index])

                    if value < personal_best_values[index]:
                        personal_best_positions[index] = positions[index].copy()
                        personal_best_values[index] = value
                        if value < global_best_value:
                            step_size = float(
                                np.linalg.norm(global_best_position - positions[index])
                            )
                            if abs(global_best_value - value) <= _MINFUNC:
                                termination = "converged_minfunc"
                                return SearchResult(
                                    positions[index].copy(),
                                    value,
                                    iterations,
                                    counted.evaluations,
                                    termination,
                                )
                            if step_size <= _MINSTEP:
                                termination = "converged_minstep"
                                return SearchResult(
                                    positions[index].copy(),
                                    value,
                                    iterations,
                                    counted.evaluations,
                                    termination,
                                )
                            global_best_position = positions[index].copy()
                            global_best_value = value
        except (EvaluationBudgetExhaustedError, TimeLimitExceededError) as error:
            vector, value = counted.best()
            return SearchResult(
                vector,
                value,
                _iterations(counted.evaluations, swarm_size),
                counted.evaluations,
                error.termination_reason,
            )

    return SearchResult(
        global_best_position,
        global_best_value,
        iterations,
        counted.evaluations,
        termination,
    )


def _iterations(evaluations: int, swarm_size: int) -> int:
    """Return started generations after accounting for the initial swarm."""
    return max(0, math.ceil((evaluations - swarm_size) / swarm_size))
