"""Initialization, warm starts, convergence, and stopping state."""

from collections.abc import Callable

import numpy as np

from givp.core.cache import EvaluationCache
from givp.core.convergence import ConvergenceMonitor
from givp.core.elite import ElitePool
from givp.core.helpers import _CoreConfigProto, _new_rng, logger


def _initialize_optimization_components(
    config: _CoreConfigProto,
    lower_arr: np.ndarray | None = None,
    upper_arr: np.ndarray | None = None,
) -> tuple[ElitePool | None, EvaluationCache | None, ConvergenceMonitor | None]:
    """Create optional elite, cache, and convergence components."""
    elite_pool = (
        ElitePool(max_size=config.elite_size, lower=lower_arr, upper=upper_arr)
        if config.use_elite_pool
        else None
    )
    cache = EvaluationCache(config.cache_size) if config.use_cache else None
    monitor = (
        ConvergenceMonitor(restart_threshold=config.early_stop_threshold)
        if config.use_convergence_monitor
        else None
    )
    return elite_pool, cache, monitor


def _prepare_initial_array(
    initial_guesses: list[list[float]] | None,
    lower_arr: np.ndarray,
    upper_arr: np.ndarray,
    num_vars: int,
) -> np.ndarray:
    """Build the first candidate from a warm start or random sample."""
    if initial_guesses:
        return np.array(initial_guesses[0], dtype=float)
    rng = _new_rng()
    return np.asarray(
        lower_arr + (upper_arr - lower_arr) * rng.random(size=num_vars)
    )


def _maybe_apply_warm_start(
    initial_guesses: list[list[float]] | None,
    elite_pool: ElitePool | None,
    cost_fn: Callable,
    best_cost: float,
    best_solution: np.ndarray,
    verbose: bool,
) -> tuple[float, np.ndarray, np.ndarray | None]:
    """Evaluate warm starts, update the incumbent, and seed the elite pool."""
    if not initial_guesses:
        return best_cost, best_solution, None
    warm_solution: np.ndarray | None = None
    warm_cost = float("inf")
    for index, initial_guess in enumerate(initial_guesses):
        candidate = np.array(initial_guess, dtype=float)
        candidate_cost = cost_fn(candidate)
        if elite_pool is not None:
            elite_pool.add(candidate.copy(), candidate_cost)
        if candidate_cost < warm_cost:
            warm_cost, warm_solution = candidate_cost, candidate.copy()
        if verbose:
            logger.info("[P14 warm-start] seed %d cost = %.2f", index, candidate_cost)
    if warm_solution is not None and warm_cost < best_cost:
        best_cost, best_solution = warm_cost, warm_solution.copy()
    return best_cost, best_solution, warm_solution


def _handle_convergence_monitor(
    monitor: ConvergenceMonitor | None,
    best_cost: float,
    elite_pool: ElitePool | None,
    verbose: bool,
) -> int:
    """Apply convergence-monitor restarts and return stagnation reset state."""
    if monitor is None:
        return 0
    status = monitor.update(best_cost, elite_pool)
    if not status["should_restart"]:
        return -1
    if elite_pool is not None and elite_pool.size() > 2:
        best_two = elite_pool.get_all()[:2]
        elite_pool.clear()
        for solution, cost in best_two:
            elite_pool.add(solution, cost)
    if verbose:
        logger.info("Convergence monitor triggered partial restart of elite pool")
    return 0


def _check_early_stopping(
    monitor: ConvergenceMonitor | None,
    config: _CoreConfigProto,
    verbose: bool,
) -> bool:
    """Return whether convergence-based early stopping is due."""
    if monitor is None or monitor.no_improve_count < config.early_stop_threshold:
        return False
    if verbose:
        logger.info("EARLY STOP: %d iterações sem melhoria", monitor.no_improve_count)
    return True
