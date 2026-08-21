"""One-variable flip neighborhood and its continuous/integer sweeps."""

from collections.abc import Callable

import numpy as np

from givp.core.helpers import _expired, _get_half, _new_rng
from givp.core.vnd.moves import _try_continuous_move_module, _try_integer_moves_module


def _search_integer_flip_module(
    sol: np.ndarray,
    best_benefit: float,
    indices: np.ndarray,
    cost_fn: Callable,
    lower_arr: np.ndarray | None,
    upper_arr: np.ndarray | None,
    first_improvement: bool,
    deadline: float = 0.0,
) -> tuple[np.ndarray, float]:
    """Sweep integer variables, applying one-variable moves."""
    best_sol = sol.copy()
    best_ben = best_benefit
    for count, index in enumerate(indices):
        if count % 8 == 0 and _expired(deadline):
            break
        new_sol, new_ben, improved = _try_integer_moves_module(
            index, sol, best_ben, cost_fn, lower_arr, upper_arr
        )
        if improved:
            best_ben, best_sol = new_ben, new_sol.copy()
            if first_improvement:
                return best_sol, best_ben
    return best_sol, best_ben


def _search_continuous_flip_module(
    sol: np.ndarray,
    best_benefit: float,
    indices: np.ndarray,
    cost_fn: Callable,
    rng: np.random.Generator,
    lower_arr: np.ndarray | None,
    upper_arr: np.ndarray | None,
    first_improvement: bool,
    deadline: float = 0.0,
) -> tuple[np.ndarray, float]:
    """Sweep continuous variables, applying small perturbations."""
    best_sol = sol.copy()
    best_ben = best_benefit
    for count, index in enumerate(indices):
        if count % 8 == 0 and _expired(deadline):
            break
        old_val = sol[index]
        changed, new_ben = _try_continuous_move_module(
            index, sol, best_ben, cost_fn, rng, lower_arr, upper_arr
        )
        if changed:
            best_ben, best_sol = new_ben, sol.copy()
            if first_improvement:
                return best_sol, best_ben
        sol[index] = old_val
    return best_sol, best_ben


def _neighborhood_flip(
    cost_fn: Callable,
    solution: np.ndarray,
    current_benefit: float,
    num_vars: int,
    first_improvement: bool = True,
    seed: int | None = None,
    lower_arr: np.ndarray | None = None,
    upper_arr: np.ndarray | None = None,
    sensitivity: np.ndarray | None = None,
    deadline: float = 0.0,
) -> tuple[np.ndarray, float]:
    """Explore one-variable moves, prioritizing sensitive variables."""
    rng = _new_rng(seed)
    half = _get_half(num_vars)
    if sensitivity is not None and np.any(sensitivity > 0):
        noise = rng.uniform(0, 0.1, size=num_vars) * np.max(sensitivity)
        indices = np.argsort(-(sensitivity + noise))
    else:
        indices = rng.permutation(num_vars)
    best_solution = solution.copy()
    best_benefit = current_benefit
    int_solution, int_benefit = _search_integer_flip_module(
        solution,
        best_benefit,
        indices[indices >= half],
        cost_fn,
        lower_arr,
        upper_arr,
        first_improvement,
        deadline,
    )
    if int_benefit < best_benefit:
        best_solution, best_benefit = int_solution, int_benefit
    cont_solution, cont_benefit = _search_continuous_flip_module(
        solution,
        best_benefit,
        indices[indices < half],
        cost_fn,
        rng,
        lower_arr,
        upper_arr,
        first_improvement,
        deadline,
    )
    if cont_benefit < best_benefit:
        best_solution, best_benefit = cont_solution, cont_benefit
    return best_solution, best_benefit
