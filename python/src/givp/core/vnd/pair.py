"""Paired continuous/integer neighbourhood for VND."""

from __future__ import annotations

from collections.abc import Callable

import numpy as np

from givp.core.helpers import _expired, _get_half, _new_rng


def _neighborhood_swap(
    cost_fn: Callable,
    solution: np.ndarray,
    current_benefit: float,
    num_vars: int,
    first_improvement: bool = True,
    max_attempts: int = 50,
    lower_arr: np.ndarray | None = None,
    upper_arr: np.ndarray | None = None,
    deadline: float = 0.0,
) -> tuple[np.ndarray, float]:
    """Perturb one continuous variable and its paired integer variable."""
    best_solution = solution.copy()
    best_benefit = current_benefit
    rng = _new_rng()
    half = _get_half(num_vars)
    if half <= 0 or half >= num_vars:
        return best_solution, best_benefit
    for _ in range(max_attempts):
        if _expired(deadline):
            break
        continuous_index = rng.integers(0, half)
        integer_index = continuous_index + half
        old_continuous = solution[continuous_index]
        old_integer = solution[integer_index]
        if lower_arr is not None and upper_arr is not None:
            continuous_span = upper_arr[continuous_index] - lower_arr[continuous_index]
            solution[continuous_index] = float(
                np.clip(
                    old_continuous + rng.uniform(-0.08 * continuous_span, 0.08 * continuous_span),
                    lower_arr[continuous_index], upper_arr[continuous_index],
                )
            )
            lower_integer = int(np.ceil(lower_arr[integer_index]))
            upper_integer = int(np.floor(upper_arr[integer_index]))
            candidate = int(np.rint(old_integer)) + int(rng.integers(-1, 2))
            solution[integer_index] = float(np.clip(candidate, lower_integer, upper_integer))
        else:
            solution[continuous_index] = old_continuous + rng.uniform(-0.1, 0.1)
            solution[integer_index] = float(
                int(np.rint(old_integer)) + int(rng.integers(-1, 2))
            )
        cost = cost_fn(solution)
        if cost < best_benefit:
            best_benefit = cost
            best_solution = solution.copy()
            if first_improvement:
                return best_solution, best_benefit
        solution[continuous_index] = old_continuous
        solution[integer_index] = old_integer
    return best_solution, best_benefit
