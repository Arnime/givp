"""Coordination of the GRASP construction phase."""

import logging
from collections.abc import Callable

import numpy as np

from givp.core.cache import EvaluationCache
from givp.core.engine.candidates import _build_candidate_pool, _build_seed_candidate
from givp.core.engine.evaluation import _evaluate_candidates_batch
from givp.core.engine.rcl import _select_from_rcl
from givp.core.engine.validation import _validate_bounds_and_initial
from givp.core.helpers import _CoreConfigProto, _get_half, _new_rng

_log = logging.getLogger(__name__)


def construct_grasp(
    num_vars: int,
    lower_arr: np.ndarray,
    upper_arr: np.ndarray,
    evaluator: Callable,
    initial_guess: np.ndarray | None,
    alpha: float,
    seed: int | None = None,
    num_candidates_per_step: int | None = None,
    cache: EvaluationCache | None = None,
    n_workers: int = 1,
) -> np.ndarray:
    """Build an initial solution through randomized sampling and RCL selection."""
    rng = _new_rng(seed)
    _validate_bounds_and_initial(lower_arr, upper_arr, initial_guess, num_vars)
    candidate_count = max(num_candidates_per_step or 10, 5)
    candidates: list[np.ndarray] = []
    costs: list[float] = []
    seed_data = _build_seed_candidate(
        initial_guess, num_vars, evaluator, lower_arr, upper_arr, cache
    )
    if seed_data is not None:
        seed_candidate, seed_cost = seed_data
        candidates.append(seed_candidate)
        costs.append(seed_cost)
        candidate_count -= 1
    candidates.extend(
        _build_candidate_pool(
            candidate_count,
            num_vars,
            _get_half(num_vars),
            lower_arr,
            upper_arr,
            rng,
        )
    )
    costs.extend(
        _evaluate_candidates_batch(
            candidates, len(costs), evaluator, cache, n_workers
        )
    )
    chosen = _select_from_rcl(np.asarray(costs), alpha, rng)
    if chosen is None:
        _log.warning("All candidate costs are non-finite; returning first candidate.")
        return candidates[0]
    return candidates[chosen]


def get_current_alpha(iteration: int, config: _CoreConfigProto) -> float:
    """Return static or linearly adapted alpha for the current iteration."""
    if config.adaptive_alpha:
        progress = iteration / max(1, config.max_iterations - 1)
        alpha = config.alpha_min + (config.alpha_max - config.alpha_min) * progress
        return float(np.clip(alpha, config.alpha_min, config.alpha_max))
    return float(config.alpha)
