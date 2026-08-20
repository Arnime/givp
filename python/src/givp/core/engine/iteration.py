"""One complete GRASP, VND, ILS, and Path Relinking iteration."""

from collections.abc import Callable

import numpy as np

from givp.core.cache import EvaluationCache
from givp.core.convergence import ConvergenceMonitor
from givp.core.elite import ElitePool
from givp.core.engine.callbacks import _print_iteration_status, _safe_iteration_callback
from givp.core.engine.construction import construct_grasp, get_current_alpha
from givp.core.engine.evaluation import _evaluate_solution_with_cache
from givp.core.engine.relinking import do_path_relinking
from givp.core.engine.state import _handle_convergence_monitor
from givp.core.helpers import _CoreConfigProto, _get_half, _new_rng, logger
from givp.core.ils import ils_search
from givp.core.vnd import local_search_vnd

EngineCallbacks = tuple[
    Callable | None,
    ElitePool | None,
    EvaluationCache | None,
    ConvergenceMonitor | None,
]


def _reactive_restart(
    cost_fn: Callable,
    num_vars: int,
    lower_arr: np.ndarray,
    upper_arr: np.ndarray,
    config: _CoreConfigProto,
    elite_pool: ElitePool | None,
    cache: EvaluationCache | None,
    best_cost: float,
    best_solution: np.ndarray,
    verbose: bool,
    deadline: float,
) -> tuple[float, np.ndarray]:
    """Diversify a stagnant search with a randomized VND/ILS restart."""
    if verbose:
        logger.info("Stagnation detected — partial restart")
    candidate = lower_arr + (upper_arr - lower_arr) * _new_rng().random(num_vars)
    candidate[_get_half(num_vars) :] = np.rint(candidate[_get_half(num_vars) :])
    candidate = local_search_vnd(
        cost_fn, candidate, num_vars, max_iter=config.vnd_iterations,
        lower_arr=lower_arr, upper_arr=upper_arr, cache=cache, deadline=deadline,
    )
    candidate_cost = cost_fn(candidate)
    candidate, candidate_cost = ils_search(
        candidate, candidate_cost, num_vars, cost_fn, config,
        lower_arr=lower_arr, upper_arr=upper_arr, cache=cache, deadline=deadline,
    )
    if candidate_cost < best_cost:
        best_cost, best_solution = candidate_cost, candidate.copy()
    if config.use_elite_pool and elite_pool is not None:
        elite_pool.add(candidate, candidate_cost)
    return best_cost, best_solution


def _run_iteration_step(
    iter_idx: int,
    cost_fn: Callable,
    num_vars: int,
    lower_arr: np.ndarray,
    upper_arr: np.ndarray,
    initial_guess: np.ndarray | None,
    config: _CoreConfigProto,
    callbacks: EngineCallbacks,
    verbose: bool,
    state: tuple[float, np.ndarray, int],
    deadline: float = 0.0,
    start_time: float | None = None,
) -> tuple[float, np.ndarray, int]:
    """Execute one complete metaheuristic iteration."""
    callback, elite_pool, cache, monitor = callbacks
    best_cost, best_solution, stagnation = state
    alpha = get_current_alpha(iter_idx, config)
    solution = construct_grasp(
        num_vars, lower_arr, upper_arr, cost_fn, initial_guess, alpha=alpha,
        num_candidates_per_step=config.num_candidates_per_step,
        cache=cache, n_workers=config.n_workers,
    )
    solution = local_search_vnd(
        cost_fn, solution, num_vars, config.vnd_iterations,
        lower_arr=lower_arr, upper_arr=upper_arr, cache=cache, deadline=deadline,
    )
    solution_cost = _evaluate_solution_with_cache(solution, cost_fn, cache)
    solution, _ = ils_search(
        solution, solution_cost, num_vars, cost_fn, config,
        lower_arr=lower_arr, upper_arr=upper_arr, cache=cache, deadline=deadline,
    )
    cost = _evaluate_solution_with_cache(solution, cost_fn, cache)
    _safe_iteration_callback(callback, iter_idx, cost, solution, verbose)
    if cost < best_cost:
        best_cost, best_solution, stagnation = cost, solution.copy(), 0
    else:
        stagnation += 1
    if config.use_elite_pool and elite_pool is not None:
        elite_pool.add(solution, cost)
    monitored_stagnation = _handle_convergence_monitor(
        monitor, best_cost, elite_pool, verbose
    )
    if monitored_stagnation >= 0:
        stagnation = monitored_stagnation
    best_cost, best_solution, stagnation = do_path_relinking(
        iter_idx, best_cost, best_solution, stagnation, config, elite_pool,
        cost_fn, num_vars, cache, deadline,
    )
    _print_iteration_status(
        verbose, iter_idx, config.max_iterations, cost, best_cost, state[0],
        alpha=alpha, stagnation=stagnation,
        elite_size=elite_pool.size() if elite_pool is not None else 0,
        start_time=start_time,
    )
    if stagnation > config.max_iterations // 4:
        best_cost, best_solution = _reactive_restart(
            cost_fn, num_vars, lower_arr, upper_arr, config, elite_pool, cache,
            best_cost, best_solution, verbose, deadline,
        )
        stagnation = 0
    return best_cost, best_solution, stagnation
