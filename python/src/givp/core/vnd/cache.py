"""Objective-function caching used by VND searches."""

from __future__ import annotations

from collections.abc import Callable

import numpy as np

from givp.core.cache import EvaluationCache


def _create_cached_cost_fn(
    cost_fn: Callable, cache: EvaluationCache | None
) -> Callable:
    """Wrap an objective function with the optional VND evaluation cache."""

    def cached_cost_fn(solution: np.ndarray) -> float:
        if cache is not None:
            cached = cache.get(solution)
            if cached is not None:
                return cached
        cost: float = cost_fn(solution)
        if cache is not None:
            cache.put(solution, cost)
        return cost

    return cached_cost_fn
