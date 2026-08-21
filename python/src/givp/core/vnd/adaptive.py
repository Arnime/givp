"""Adaptive Variable Neighborhood Descent."""

from collections.abc import Callable

import numpy as np

from givp.core.cache import EvaluationCache
from givp.core.helpers import _new_rng
from givp.core.vnd.cache import _create_cached_cost_fn
from givp.core.vnd.dispatch import _execute_neighborhood


def local_search_vnd_adaptive(
    cost_fn: Callable,
    solution: np.ndarray,
    num_vars: int,
    max_iter: int = 300,
    use_first_improvement: bool = True,
    no_improve_limit: int = 5,
    lower_arr: np.ndarray | None = None,
    upper_arr: np.ndarray | None = None,
    cache: EvaluationCache | None = None,
    reward_factor: float = 1.0,
    decay_factor: float = 0.95,
    min_probability: float = 0.05,
) -> np.ndarray:
    """Run VND with adaptive roulette-wheel neighborhood selection."""
    current_solution = np.array(solution, dtype=float)
    cached_cost_fn = _create_cached_cost_fn(cost_fn, cache)
    current_benefit = cached_cost_fn(current_solution)
    sensitivity = np.zeros(num_vars, dtype=float)
    scores = np.ones(5, dtype=float)
    rng = _new_rng()
    iteration = 0
    no_improve_count = 0
    while iteration < max_iter and no_improve_count < no_improve_limit:
        iteration += 1
        old_benefit = current_benefit
        old_solution = current_solution.copy()
        probabilities = np.maximum(scores / scores.sum(), min_probability)
        probabilities /= probabilities.sum()
        neighborhood_idx = int(rng.choice(5, p=probabilities))
        candidate, benefit = _execute_neighborhood(
            neighborhood_idx, cached_cost_fn, current_solution, current_benefit,
            num_vars, use_first_improvement, lower_arr, upper_arr, sensitivity,
        )
        if benefit < current_benefit:
            improvement = current_benefit - benefit
            np.copyto(current_solution, candidate)
            current_benefit = benefit
            scores[neighborhood_idx] += (
                reward_factor * improvement / max(abs(old_benefit), 1e-10)
            )
            sensitivity[np.abs(current_solution - old_solution) > 1e-12] += improvement
            sensitivity *= 0.9
            no_improve_count = 0
        else:
            no_improve_count += 1
        np.maximum(scores * decay_factor, 0.01, out=scores)
    return current_solution
