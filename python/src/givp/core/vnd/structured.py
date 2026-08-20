"""Structured group and block neighborhoods for VND."""

from collections.abc import Callable

import numpy as np

from givp.core.helpers import _expired, _new_rng
from givp.core.vnd.layout import (
    _apply_block_perturbation,
    _apply_group_perturbation,
    _group_layout,
)


def _neighborhood_group(
    cost_fn: Callable,
    solution: np.ndarray,
    current_benefit: float,
    num_vars: int,
    first_improvement: bool = True,
    max_attempts: int = 30,
    lower_arr: np.ndarray | None = None,
    upper_arr: np.ndarray | None = None,
    deadline: float = 0.0,
) -> tuple[np.ndarray, float]:
    """Perturb all steps of one configured group simultaneously."""
    best_solution = solution.copy()
    best_benefit = current_benefit
    rng = _new_rng()
    layout = _group_layout(num_vars)
    if layout is None or lower_arr is None or upper_arr is None:
        return best_solution, best_benefit
    half, n_groups, n_steps = layout
    for _ in range(max_attempts):
        if _expired(deadline):
            break
        group_idx = rng.integers(0, n_groups)
        start = int(group_idx * n_steps)
        end = start + n_steps
        old_cont = solution[start:end].copy()
        old_int = solution[half + start : half + end].copy()
        _apply_group_perturbation(
            solution, old_cont, old_int, start, half, n_steps,
            lower_arr, upper_arr, rng,
        )
        cost = cost_fn(solution)
        if cost < best_benefit:
            best_benefit = cost
            best_solution = solution.copy()
            if first_improvement:
                return best_solution, best_benefit
        solution[start:end] = old_cont
        solution[half + start : half + end] = old_int
    return best_solution, best_benefit


def _neighborhood_block(
    cost_fn: Callable,
    solution: np.ndarray,
    current_benefit: float,
    num_vars: int,
    first_improvement: bool = True,
    max_attempts: int = 30,
    lower_arr: np.ndarray | None = None,
    upper_arr: np.ndarray | None = None,
    deadline: float = 0.0,
) -> tuple[np.ndarray, float]:
    """Perturb a contiguous step block across all configured groups."""
    best_solution = solution.copy()
    best_benefit = current_benefit
    rng = _new_rng()
    layout = _group_layout(num_vars)
    if layout is None or lower_arr is None or upper_arr is None:
        return best_solution, best_benefit
    half, n_groups, n_steps = layout
    for _ in range(max_attempts):
        if _expired(deadline):
            break
        block_size = rng.integers(3, min(7, n_steps + 1))
        block_start = int(rng.integers(0, n_steps - block_size + 1))
        block_end = int(block_start + block_size)
        old_vals = solution.copy()
        _apply_block_perturbation(
            solution, old_vals, half, n_groups, n_steps, block_start,
            block_end, lower_arr, upper_arr, rng.uniform(-0.04, 0.04),
        )
        cost = cost_fn(solution)
        if cost < best_benefit:
            best_benefit = cost
            best_solution = solution.copy()
            if first_improvement:
                return best_solution, best_benefit
        np.copyto(solution, old_vals)
    return best_solution, best_benefit
