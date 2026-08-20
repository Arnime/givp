# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
"""Adapters for Pymoo literature baselines."""

from __future__ import annotations

import numpy as np
from pymoo.algorithms.soo.nonconvex.cmaes import CMAES
from pymoo.algorithms.soo.nonconvex.ga import GA
from pymoo.algorithms.soo.nonconvex.pso import PSO
from pymoo.optimize import minimize
from pymoo.problems.functional import FunctionalProblem

from benchmarks.common.models import Objective


def run_pymoo(
    algorithm_name: str,
    objective: Objective,
    bounds: list[tuple[float, float]],
    seed: int,
    max_iter: int,
) -> tuple[float, int, int]:
    """Run a supported Pymoo single-objective optimizer."""
    lower = np.asarray([low for low, _ in bounds], dtype=float)
    upper = np.asarray([high for _, high in bounds], dtype=float)
    problem = FunctionalProblem(
        n_var=len(bounds),
        objs=lambda values: float(objective(np.asarray(values, dtype=float))),
        xl=lower,
        xu=upper,
    )

    if algorithm_name == "PSO":
        algorithm = PSO()
    elif algorithm_name == "GA":
        algorithm = GA()
    elif algorithm_name == "CMA-ES":
        initial = np.random.default_rng(seed).uniform(lower, upper)
        algorithm = CMAES(x0=initial)
    else:
        raise ValueError(f"unknown Pymoo algorithm: {algorithm_name!r}")

    result = minimize(
        problem,
        algorithm,
        ("n_gen", max_iter),
        seed=seed,
        verbose=False,
    )
    value = float(np.asarray(result.F, dtype=float).reshape(-1)[0])
    evaluations = int(getattr(result.algorithm.evaluator, "n_eval", 0))
    return value, max_iter, evaluations
