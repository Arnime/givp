# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
"""Particle swarm exactly as the SOG ``PSO`` wrapper invokes it.

SOG (``app/internal/modules/algoritmo/otimizacao/pso.py``) calls
``pyswarm.pso`` 0.6 with ``swarmsize``, ``omega``, ``phip``, ``phig`` and
``maxiter`` only, after a global ``np.random.seed``. pyswarm 0.6 keeps its
default ``minstep``/``minfunc`` of ``1e-8`` and stops early on either. The
validated benchmark controls are 200 particles, 250 iterations, ``omega=0.5``
and ``c1=c2=1.0``. See ``SOG_ALGORITHM_MAPPING.md``.
"""

from __future__ import annotations

import io
import math
from collections.abc import Callable, Mapping
from contextlib import redirect_stdout

import numpy as np
from numpy.typing import NDArray
from pyswarm import pso

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

_STOP_REASONS = (
    ("maximum iterations reached", "max_iterations"),
    ("objective change less than", "converged_minfunc"),
    ("position change less than", "converged_minstep"),
)


def run_pso(
    objective: Callable[[NDArray[np.float64]], float],
    bounds: list[tuple[float, float]],
    profile: Mapping[str, object],
    seed: int | None,
) -> SearchResult:
    """Minimize ``objective`` with pyswarm 0.6 and the profile's coefficients."""
    counted = CountingObjective(
        objective,
        optional_integer(profile, "max_evaluations"),
        optional_number(profile, "time_limit_seconds"),
    )
    swarm_size = integer(profile, "population_size")
    # pyswarm 0.6 reports why it stopped only on stdout.
    stdout = io.StringIO()
    with seeded_global_numpy(seed), redirect_stdout(stdout):
        try:
            vector, value = pso(
                counted,
                [bound[0] for bound in bounds],
                [bound[1] for bound in bounds],
                swarmsize=swarm_size,
                omega=number(profile, "inertia"),
                phip=number(profile, "c1"),
                phig=number(profile, "c2"),
                maxiter=integer(profile, "max_generations"),
            )
            termination = _termination(stdout.getvalue())
        except (EvaluationBudgetExhaustedError, TimeLimitExceededError) as error:
            vector, value = counted.best()
            termination = error.termination_reason
    return SearchResult(
        np.asarray(vector, dtype=np.float64),
        float(value),
        _iterations(counted.evaluations, swarm_size),
        counted.evaluations,
        termination,
    )


def _iterations(evaluations: int, swarm_size: int) -> int:
    """Return the started swarm iterations after the initial evaluation sweep."""
    return max(0, math.ceil((evaluations - swarm_size) / swarm_size))


def _termination(output: str) -> str:
    for line in reversed(output.splitlines()):
        for marker, reason in _STOP_REASONS:
            if marker in line:
                return reason
    return "pyswarm_returned"
