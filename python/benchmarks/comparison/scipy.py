# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
"""Adapters for SciPy literature baselines."""

from __future__ import annotations

import numpy as np
from scipy.optimize import differential_evolution, dual_annealing

from benchmarks.common.models import Objective


def run_de(
    objective: Objective,
    bounds: list[tuple[float, float]],
    seed: int,
    max_iter: int,
) -> tuple[float, int, int]:
    """Run SciPy Differential Evolution."""
    np.random.seed(seed)
    result = differential_evolution(
        objective,
        bounds,
        maxiter=max_iter,
        tol=1e-12,
        workers=1,
    )
    return float(result.fun), int(result.nit), int(result.nfev)


def run_sa(
    objective: Objective,
    bounds: list[tuple[float, float]],
    seed: int,
    max_iter: int,
) -> tuple[float, int, int]:
    """Run SciPy Dual Annealing."""
    rng = np.random.default_rng(seed)
    np.random.seed(seed)
    initial = np.array([low + rng.random() * (high - low) for low, high in bounds])
    result = dual_annealing(
        objective,
        bounds,
        maxiter=max_iter * 100,
        x0=initial,
    )
    return float(result.fun), int(result.nit), int(result.nfev)
