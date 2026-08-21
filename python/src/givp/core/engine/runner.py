"""Public optimizer orchestration and the main GRASP loop."""

from collections.abc import Callable

import numpy as np

from givp.config import GIVPConfig
from givp.core.cache import EvaluationCache
from givp.core.convergence import ConvergenceMonitor
from givp.core.elite import ElitePool
from givp.core.engine.callbacks import (
    _print_cache_stats,
    _print_run_footer,
    _print_run_header,
)
from givp.core.engine.iteration import _run_iteration_step
from givp.core.engine.state import (
    _check_early_stopping,
    _initialize_optimization_components,
    _maybe_apply_warm_start,
    _prepare_initial_array,
)
from givp.core.engine.validation import _prepare_bounds
from givp.core.helpers import (
    _CoreConfigProto,
    _expired,
    _set_group_size,
    _set_integer_split,
    _time_mod,
    logger,
)


def _run_grasp_loop(
    cost_fn: Callable,
    num_vars: int,
    config: _CoreConfigProto,
    lower_arr: np.ndarray,
    upper_arr: np.ndarray,
    initial_arr: np.ndarray,
    callbacks: tuple[
        Callable | None,
        ElitePool | None,
        EvaluationCache | None,
        ConvergenceMonitor | None,
    ],
    verbose: bool,
    state: tuple[float, np.ndarray, int],
) -> tuple[float, np.ndarray, int, int, str]:
    """Execute GRASP iterations until a configured stopping condition is met."""
    _, _, _, monitor = callbacks
    best_cost, best_solution, stagnation = state
    start_time = _time_mod.monotonic()
    deadline = start_time + config.time_limit if config.time_limit > 0 else 0.0
    _print_run_header(verbose, num_vars, config)
    actual_nit = 0
    termination = "max_iterations"
    for iteration in range(config.max_iterations):
        if _expired(deadline):
            if verbose:
                logger.info(
                    "TIME LIMIT: %.0fs atingido na iteração %d",
                    config.time_limit, iteration + 1,
                )
            termination = "time limit"
            break
        best_cost, best_solution, stagnation = _run_iteration_step(
            iteration, cost_fn, num_vars, lower_arr, upper_arr, initial_arr,
            config, callbacks, verbose, (best_cost, best_solution, stagnation),
            deadline=deadline, start_time=start_time,
        )
        actual_nit = iteration + 1
        if _check_early_stopping(monitor, config, verbose):
            termination = "early_stop"
            break
    _print_run_footer(verbose, best_cost, stagnation, start_time)
    return best_cost, best_solution, stagnation, actual_nit, termination


def grasp_ils_vnd(
    cost_fn: Callable,
    num_vars: int,
    config: _CoreConfigProto | None = None,
    verbose: bool = False,
    iteration_callback: Callable | None = None,
    lower: list[float] | None = None,
    upper: list[float] | None = None,
    initial_guesses: list[list[float]] | None = None,
) -> tuple[list[int], float, int, str]:
    """Run the GRASP-ILS-VND-PR optimizer and return its best result."""
    if config is None:
        config = GIVPConfig()
    lower_arr, upper_arr = _prepare_bounds(lower, upper)
    _set_integer_split(config.integer_split)
    _set_group_size(config.group_size)
    initial_arr = _prepare_initial_array(
        initial_guesses, lower_arr, upper_arr, num_vars
    )
    elite_pool, cache, monitor = _initialize_optimization_components(
        config, lower_arr, upper_arr
    )
    best_solution = np.zeros(num_vars, dtype=float)
    best_cost, stagnation = float("inf"), 0
    best_cost, best_solution, warm_solution = _maybe_apply_warm_start(
        initial_guesses, elite_pool, cost_fn, best_cost, best_solution, verbose
    )
    if warm_solution is not None:
        initial_arr = warm_solution
    best_cost, best_solution, _, actual_nit, termination = _run_grasp_loop(
        cost_fn, num_vars, config, lower_arr, upper_arr, initial_arr,
        (iteration_callback, elite_pool, cache, monitor), verbose,
        (best_cost, best_solution, stagnation),
    )
    _print_cache_stats(cache, verbose)
    return best_solution.tolist(), best_cost, actual_nit, termination
