"""Elite-pool Path Relinking stage of the optimizer."""

from collections.abc import Callable

import numpy as np

from givp.core.cache import EvaluationCache
from givp.core.elite import ElitePool
from givp.core.helpers import _CoreConfigProto, _expired, _new_rng
from givp.core.pr import bidirectional_path_relinking, path_relinking
from givp.core.vnd import local_search_vnd
from givp.core.vnd.cache import _create_cached_cost_fn


def _apply_path_relinking_to_pair(
    source: np.ndarray,
    target: np.ndarray,
    cached_fn: Callable,
    num_vars: int,
    config: _CoreConfigProto,
    cache: EvaluationCache | None,
    deadline: float = 0.0,
) -> tuple[np.ndarray, float]:
    """Relink one elite pair and refine the result with VND."""
    if config.path_relink_strategy == "bidirectional":
        solution, _ = bidirectional_path_relinking(
            cached_fn, source, target, deadline=deadline
        )
    elif config.path_relink_strategy == "backward":
        solution, _ = path_relinking(
            cached_fn, target, source, strategy="forward", deadline=deadline
        )
    elif config.path_relink_strategy in ("randomized", "random"):
        if _new_rng().integers(0, 2) == 0:
            solution, _ = path_relinking(
                cached_fn, source, target, strategy="forward", deadline=deadline
            )
        else:
            solution, _ = path_relinking(
                cached_fn, target, source, strategy="forward", deadline=deadline
            )
    else:
        solution, _ = path_relinking(
            cached_fn, source, target, strategy="forward", deadline=deadline
        )
    solution = local_search_vnd(
        cached_fn,
        solution,
        num_vars,
        max_iter=config.vnd_iterations // 2,
        cache=cache,
        deadline=deadline,
    )
    return solution, cached_fn(solution)


def _process_path_relinking_pairs(
    elite_solutions: list[tuple[np.ndarray, float]],
    cost_fn: Callable,
    num_vars: int,
    config: _CoreConfigProto,
    best_cost: float,
    best_solution: np.ndarray,
    stagnation: int,
    elite_pool: ElitePool,
    cache: EvaluationCache | None,
    deadline: float = 0.0,
) -> tuple[float, np.ndarray, int]:
    """Relink the leading pairs from the elite pool."""
    cached_fn = _create_cached_cost_fn(cost_fn, cache)
    for first in range(min(3, len(elite_solutions))):
        for second in range(first + 1, min(4, len(elite_solutions))):
            if _expired(deadline):
                break
            solution, cost = _apply_path_relinking_to_pair(
                elite_solutions[first][0], elite_solutions[second][0], cached_fn,
                num_vars, config, cache, deadline,
            )
            if cost < best_cost:
                best_cost, best_solution, stagnation = cost, solution.copy(), 0
            elite_pool.add(solution, cost)
    return best_cost, best_solution, stagnation


def do_path_relinking(
    iteration: int,
    best_cost: float,
    best_solution: np.ndarray,
    stagnation: int,
    config: _CoreConfigProto,
    elite_pool: ElitePool | None,
    cost_fn: Callable,
    num_vars: int,
    cache: EvaluationCache | None = None,
    deadline: float = 0.0,
) -> tuple[float, np.ndarray, int]:
    """Run scheduled Path Relinking when the elite pool is ready."""
    enabled = (
        config.use_elite_pool
        and elite_pool is not None
        and iteration > 0
        and iteration % config.path_relink_frequency == 0
        and elite_pool.size() >= 2
    )
    if not enabled or elite_pool is None:
        return best_cost, best_solution, stagnation
    return _process_path_relinking_pairs(
        elite_pool.get_all(), cost_fn, num_vars, config, best_cost,
        best_solution, stagnation, elite_pool, cache, deadline,
    )
