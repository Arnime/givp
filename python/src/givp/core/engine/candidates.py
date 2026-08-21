"""Candidate generation for the GRASP construction phase."""

from collections.abc import Callable

import numpy as np

from givp.core.cache import EvaluationCache
from givp.core.engine.evaluation import _evaluate_with_cache
from givp.core.helpers import EvaluatorFn, _get_half, _new_rng, _safe_evaluate


def _seed_from_initial(
    chute: np.ndarray,
    num_vars: int,
    evaluator: EvaluatorFn,
    lower_arr: np.ndarray,
    upper_arr: np.ndarray,
) -> np.ndarray:
    """Use a finite initial guess or replace it with a random candidate."""
    if np.isfinite(_safe_evaluate(evaluator, chute)):
        return chute.copy()
    rng = _new_rng()
    return np.asarray(lower_arr + (upper_arr - lower_arr) * rng.random(num_vars))


def _normalize_integer_tail(solution: np.ndarray, half: int) -> None:
    """Round integer-part variables in place."""
    if half < solution.size:
        solution[half:] = np.rint(solution[half:])


def _build_seed_candidate(
    initial_guess: np.ndarray | None,
    num_vars: int,
    evaluator: Callable,
    lower_arr: np.ndarray,
    upper_arr: np.ndarray,
    cache: EvaluationCache | None,
) -> tuple[np.ndarray, float] | None:
    """Build and evaluate the warm-start candidate when provided."""
    if initial_guess is None:
        return None
    candidate = _seed_from_initial(
        initial_guess, num_vars, evaluator, lower_arr, upper_arr
    )
    _normalize_integer_tail(candidate, _get_half(num_vars))
    return candidate, _evaluate_with_cache(candidate, evaluator, cache)


def _sample_integer_from_bounds(
    lower: float, upper: float, rng: np.random.Generator
) -> float:
    """Sample an integer that respects numeric bounds."""
    lo = int(np.ceil(lower))
    hi = int(np.floor(upper))
    if hi >= lo:
        return float(rng.integers(lo, hi + 1))
    return float(int(np.rint((lower + upper) / 2.0)))


def _build_heuristic_candidate(
    num_vars: int,
    half: int,
    lower_arr: np.ndarray,
    upper_arr: np.ndarray,
    rng: np.random.Generator,
) -> np.ndarray:
    """Build a mixed candidate using proportional integer dispatch."""
    solution = np.empty(num_vars, dtype=float)
    midpoint = (lower_arr[:half] + upper_arr[:half]) / 2.0
    span = upper_arr[:half] - lower_arr[:half]
    solution[:half] = np.clip(
        midpoint + rng.uniform(-0.15, 0.15, size=half) * span,
        lower_arr[:half], upper_arr[:half],
    )
    for index in range(half, num_vars):
        lo = int(np.ceil(lower_arr[index]))
        hi = int(np.floor(upper_arr[index]))
        cont_idx = index - half
        if hi > lo and span[cont_idx] > 0:
            fraction = (solution[cont_idx] - lower_arr[cont_idx]) / span[cont_idx]
            solution[index] = float(int(np.clip(np.rint(lo + fraction * (hi - lo)), lo, hi)))
        else:
            solution[index] = float(
                hi if hi >= lo else int(np.rint((lower_arr[index] + upper_arr[index]) / 2.0))
            )
    return solution


def _build_random_candidate(
    num_vars: int,
    half: int,
    lower_arr: np.ndarray,
    upper_arr: np.ndarray,
    rng: np.random.Generator,
) -> np.ndarray:
    """Build a uniformly random mixed continuous/integer candidate."""
    solution = np.empty(num_vars, dtype=float)
    solution[:half] = lower_arr[:half] + (
        upper_arr[:half] - lower_arr[:half]
    ) * rng.random(half)
    for index in range(half, num_vars):
        solution[index] = _sample_integer_from_bounds(
            lower_arr[index], upper_arr[index], rng
        )
    return solution


def _build_candidate_pool(
    count: int,
    num_vars: int,
    half: int,
    lower_arr: np.ndarray,
    upper_arr: np.ndarray,
    rng: np.random.Generator,
) -> list[np.ndarray]:
    """Build the heuristic and random portions of a candidate pool."""
    heuristic_count = max(1, count // 2)
    return [
        *(
            _build_heuristic_candidate(num_vars, half, lower_arr, upper_arr, rng)
            for _ in range(heuristic_count)
        ),
        *(
            _build_random_candidate(num_vars, half, lower_arr, upper_arr, rng)
            for _ in range(count - heuristic_count)
        ),
    ]
