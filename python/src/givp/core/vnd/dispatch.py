"""Neighborhood dispatch and fixed-order selection for VND."""

from collections.abc import Callable

import numpy as np

from givp.core.helpers import _expired
from givp.core.vnd.flip import _neighborhood_flip
from givp.core.vnd.multiflip import _neighborhood_multiflip
from givp.core.vnd.pair import _neighborhood_swap
from givp.core.vnd.structured import _neighborhood_block, _neighborhood_group


def _execute_neighborhood(
    idx: int,
    cost_fn: Callable,
    solution: np.ndarray,
    current_benefit: float,
    num_vars: int,
    first_improvement: bool,
    lower_arr: np.ndarray | None,
    upper_arr: np.ndarray | None,
    sensitivity: np.ndarray | None,
    deadline: float = 0.0,
) -> tuple[np.ndarray, float]:
    """Dispatch one of the five neighborhoods by index."""
    if idx == 0:
        return _neighborhood_flip(
            cost_fn, solution, current_benefit, num_vars, first_improvement,
            lower_arr=lower_arr, upper_arr=upper_arr,
            sensitivity=sensitivity, deadline=deadline,
        )
    if idx == 1:
        return _neighborhood_swap(
            cost_fn, solution, current_benefit, num_vars, first_improvement,
            lower_arr=lower_arr, upper_arr=upper_arr, deadline=deadline,
        )
    if idx == 2:
        return _neighborhood_group(
            cost_fn, solution, current_benefit, num_vars, first_improvement,
            lower_arr=lower_arr, upper_arr=upper_arr, deadline=deadline,
        )
    if idx == 3:
        return _neighborhood_block(
            cost_fn, solution, current_benefit, num_vars, first_improvement,
            lower_arr=lower_arr, upper_arr=upper_arr, deadline=deadline,
        )
    return _neighborhood_multiflip(
        cost_fn, solution, current_benefit, num_vars, k=3,
        lower_arr=lower_arr, upper_arr=upper_arr, deadline=deadline,
    )


def _try_neighborhoods(
    cached_cost_fn: Callable,
    solution: np.ndarray,
    current_benefit: float,
    num_vars: int,
    use_first_improvement: bool,
    iteration: int,
    no_improve_flip_limit: int,
    lower_arr: np.ndarray | None,
    upper_arr: np.ndarray | None,
    sensitivity: np.ndarray | None = None,
    deadline: float = 0.0,
) -> tuple[np.ndarray, float, bool]:
    """Try fixed-order neighborhoods and return the first improvement."""
    for idx in range(4):
        if _expired(deadline):
            return solution, current_benefit, False
        candidate, benefit = _execute_neighborhood(
            idx, cached_cost_fn, solution, current_benefit, num_vars,
            use_first_improvement, lower_arr, upper_arr, sensitivity, deadline,
        )
        if benefit < current_benefit:
            return candidate, benefit, True
    if iteration % no_improve_flip_limit == 0 and not _expired(deadline):
        candidate, benefit = _neighborhood_multiflip(
            cached_cost_fn, solution, current_benefit, num_vars,
            k=no_improve_flip_limit, lower_arr=lower_arr,
            upper_arr=upper_arr, deadline=deadline,
        )
        if benefit < current_benefit:
            return candidate, benefit, True
    return solution, current_benefit, False
