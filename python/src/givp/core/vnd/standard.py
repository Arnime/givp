"""Standard fixed-order Variable Neighborhood Descent."""

from collections.abc import Callable

import numpy as np

from givp.core.cache import EvaluationCache
from givp.core.helpers import _expired
from givp.core.vnd.cache import _create_cached_cost_fn
from givp.core.vnd.dispatch import _try_neighborhoods


def local_search_vnd(
    cost_fn: Callable,
    solution: np.ndarray,
    num_vars: int,
    max_iter: int = 300,
    use_first_improvement: bool = True,
    no_improve_limit: int = 5,
    no_improve_flip_limit: int = 3,
    lower_arr: np.ndarray | None = None,
    upper_arr: np.ndarray | None = None,
    cache: EvaluationCache | None = None,
    deadline: float = 0.0,
) -> np.ndarray:
    """Run fixed-order Variable Neighborhood Descent."""
    solution = np.array(solution, dtype=float)
    cached_cost_fn = _create_cached_cost_fn(cost_fn, cache)
    current_benefit = cached_cost_fn(solution)
    sensitivity = np.zeros(num_vars, dtype=float)
    iteration = 0
    no_improve_count = 0
    while iteration < max_iter and no_improve_count < no_improve_limit:
        if _expired(deadline):
            break
        iteration += 1
        old_benefit = current_benefit
        old_solution = solution.copy()
        solution, current_benefit, improved = _try_neighborhoods(
            cached_cost_fn, solution, current_benefit, num_vars,
            use_first_improvement, iteration, no_improve_flip_limit,
            lower_arr, upper_arr, sensitivity, deadline,
        )
        if improved:
            no_improve_count = 0
            changed_mask = np.abs(solution - old_solution) > 1e-12
            sensitivity[changed_mask] += old_benefit - current_benefit
            sensitivity *= 0.9
        else:
            no_improve_count += 1
    return solution
