"""Candidate evaluation, caching, and parallel execution for GRASP."""

from __future__ import annotations

import logging
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from pickle import PicklingError

import cloudpickle
import numpy as np

from givp.core.cache import EvaluationCache
from givp.core.helpers import _safe_evaluate

_log = logging.getLogger(__name__)


def _evaluate_with_cache(
    cand: np.ndarray, evaluator: Callable, cache: EvaluationCache | None
) -> float:
    """Evaluate a candidate using the cache when available."""
    if cache is not None:
        cached_cost = cache.get(cand)
        if cached_cost is not None:
            return cached_cost
    cost = _safe_evaluate(evaluator, cand)
    if cache is not None and np.isfinite(cost):
        cache.put(cand, cost)
    return cost


def _evaluate_solution_with_cache(
    solution: np.ndarray,
    evaluator: Callable,
    cache: EvaluationCache | None,
) -> float:
    """Evaluate a solution using a shared cache when available."""
    return _evaluate_with_cache(solution, evaluator, cache)


def _parallel_worker(args: tuple[np.ndarray, Callable]) -> float:
    """Evaluate one picklable candidate in a process worker."""
    solution, evaluator = args
    return _safe_evaluate(evaluator, solution)


def _cloudpickle_worker(args: tuple[np.ndarray, bytes]) -> float:
    """Evaluate one candidate deserialized by cloudpickle."""
    solution, serialized = args
    evaluator = cloudpickle.loads(serialized)
    return _safe_evaluate(evaluator, solution)


def _try_standard_process_pool(
    unevaluated: list[np.ndarray], evaluator: Callable, n_workers: int
) -> tuple[list[float] | None, Exception | None]:
    """Attempt candidate evaluation using the standard process pool."""
    try:
        with ProcessPoolExecutor(max_workers=n_workers) as pool:
            return list(
                pool.map(_parallel_worker, ((item, evaluator) for item in unevaluated))
            ), None
    except (PicklingError, AttributeError, TypeError, OSError) as error:
        return None, error


def _try_cloudpickle_process_pool(
    unevaluated: list[np.ndarray], evaluator: Callable, n_workers: int
) -> tuple[list[float] | None, Exception | None]:
    """Attempt process evaluation using cloudpickle serialisation."""
    try:
        serialized = cloudpickle.dumps(evaluator)
        with ProcessPoolExecutor(max_workers=n_workers) as pool:
            return list(
                pool.map(
                    _cloudpickle_worker, ((item, serialized) for item in unevaluated)
                )
            ), None
    except (PicklingError, AttributeError, TypeError, OSError) as error:
        return None, error


def _evaluate_candidates_batch(
    candidates: list[np.ndarray],
    evaluated_count: int,
    evaluator: Callable,
    cache: EvaluationCache | None,
    n_workers: int,
) -> list[float]:
    """Evaluate remaining candidates with process and thread fallbacks."""
    unevaluated = candidates[evaluated_count:]
    if n_workers <= 1 or len(unevaluated) <= 1:
        return [_evaluate_with_cache(item, evaluator, cache) for item in unevaluated]
    if cache is None:
        process_results, _process_error = _try_standard_process_pool(
            unevaluated, evaluator, n_workers
        )
        if process_results is not None:
            return process_results
        cloudpickle_results, cloudpickle_error = _try_cloudpickle_process_pool(
            unevaluated, evaluator, n_workers
        )
        if cloudpickle_results is not None:
            return cloudpickle_results
        if cloudpickle_error is not None:
            _log.warning(
                "cloudpickle serialisation failed (%s); falling back to ThreadPoolExecutor.",
                cloudpickle_error,
            )
    if cache is not None:
        _log.warning(
            "n_workers=%d requested but use_cache=True forces ThreadPoolExecutor.",
            n_workers,
        )
    with ThreadPoolExecutor(max_workers=n_workers) as executor:
        return list(
            executor.map(
                lambda item: _evaluate_with_cache(item, evaluator, cache), unevaluated
            )
        )
