"""Multi-variable perturbation neighbourhood for VND."""

from __future__ import annotations

from collections.abc import Callable

import numpy as np

from givp.core.helpers import _expired, _new_rng
from givp.core.vnd.moves import _modify_indices_for_multiflip


def _neighborhood_multiflip(
    cost_fn: Callable,
    solution: np.ndarray,
    current_benefit: float,
    num_vars: int,
    k: int = 3,
    max_attempts: int = 50,
    seed: int | None = None,
    lower_arr: np.ndarray | None = None,
    upper_arr: np.ndarray | None = None,
    deadline: float = 0.0,
) -> tuple[np.ndarray, float]:
    """Simultaneously modify up to ``k`` variables and retain the best move."""
    best_solution = solution.copy()
    best_benefit = current_benefit
    rng = _new_rng(seed)
    for _ in range(max_attempts):
        if _expired(deadline):
            break
        indices = rng.choice(num_vars, size=min(k, num_vars), replace=False)
        old_values = _modify_indices_for_multiflip(
            solution, indices, rng, lower_arr, upper_arr
        )
        cost = cost_fn(solution)
        if cost < best_benefit:
            best_benefit = cost
            best_solution = solution.copy()
        solution[indices] = old_values
    return best_solution, best_benefit
