# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
"""Physical-evaluation accounting shared by the SOG-reproduction adapters."""

from __future__ import annotations

import math
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from time import perf_counter

import numpy as np
from numpy.typing import NDArray


class EvaluationBudgetExhaustedError(RuntimeError):
    """Raised instead of a physical evaluation once the shared cap is reached."""

    termination_reason = "evaluation_limit"


class TimeLimitExceededError(RuntimeError):
    """Raised when a run reaches its wall-clock budget."""

    termination_reason = "time_limit"


@dataclass(frozen=True)
class SearchResult:
    """What one optimizer adapter reports before the campaign re-evaluates it."""

    vector: NDArray[np.float64]
    best_objective: float
    iterations: int
    evaluations: int
    termination: str


class CountingObjective:
    """Count evaluations, keep the best point and enforce run budgets.

    The cap is exact: the call that would exceed ``max_evaluations`` raises
    :class:`EvaluationBudgetExhaustedError` without touching the simulator, so
    an interrupted optimizer has used precisely ``max_evaluations`` evaluations.
    An initial call is allowed so the optimizer has a best point to return.
    Later calls are checked before evaluation, and every call is checked after
    it returns; a call already in progress is allowed to finish.
    """

    def __init__(
        self,
        objective: Callable[[NDArray[np.float64]], float],
        max_evaluations: int | None,
        time_limit_seconds: float | None = None,
    ) -> None:
        if max_evaluations is not None and max_evaluations < 1:
            raise ValueError("max_evaluations must be positive when present")
        if time_limit_seconds is not None and (
            not math.isfinite(time_limit_seconds) or time_limit_seconds < 0
        ):
            raise ValueError("time_limit_seconds must be finite and non-negative")
        self._objective = objective
        self.max_evaluations = max_evaluations
        self._deadline = (
            perf_counter() + time_limit_seconds
            if time_limit_seconds is not None and time_limit_seconds > 0
            else None
        )
        self.evaluations = 0
        self.best_value = float("inf")
        self.best_vector: NDArray[np.float64] | None = None

    def __call__(self, vector: NDArray[np.float64]) -> float:
        self._check_time_limit()
        if (
            self.max_evaluations is not None
            and self.evaluations >= self.max_evaluations
        ):
            raise EvaluationBudgetExhaustedError(
                f"physical-evaluation budget of {self.max_evaluations} reached"
            )
        self.evaluations += 1
        candidate = np.array(vector, dtype=np.float64, copy=True).reshape(-1)
        value = float(self._objective(candidate))
        if value < self.best_value or self.best_vector is None:
            self.best_value = value
            self.best_vector = candidate
        self._check_time_limit()
        return value

    def _check_time_limit(self) -> None:
        if (
            self.evaluations > 0
            and self._deadline is not None
            and perf_counter() >= self._deadline
        ):
            raise TimeLimitExceededError("wall-clock time limit reached")

    def best(self) -> tuple[NDArray[np.float64], float]:
        """Return the best evaluated point; fails if nothing was evaluated."""
        if self.best_vector is None:
            raise RuntimeError("no physical evaluation was performed")
        return self.best_vector.copy(), self.best_value


@contextmanager
def seeded_global_numpy(seed: int | None) -> Iterator[None]:
    """Seed the legacy global NumPy RNG as SOG does, restoring it afterwards.

    SOG calls ``np.random.seed(42)`` before SciPy DE and pyswarm, neither of
    which receives an explicit seed. Both libraries then draw from the global
    ``RandomState``; restoring it keeps campaign runs isolated from each other.
    """
    state = np.random.get_state()
    try:
        if seed is not None:
            np.random.seed(seed)
        yield
    finally:
        np.random.set_state(state)


def integer(profile: Mapping[str, object], field: str) -> int:
    """Read a required integer profile field."""
    value = profile.get(field)
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"profile field {field!r} must be an integer")
    return value


def optional_integer(profile: Mapping[str, object], field: str) -> int | None:
    """Read an optional positive integer profile field."""
    value = profile.get(field)
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise TypeError(f"profile field {field!r} must be a positive integer")
    return value


def optional_number(profile: Mapping[str, object], field: str) -> float | None:
    """Read an optional numeric profile field."""
    if profile.get(field) is None:
        return None
    return number(profile, field)


def number(profile: Mapping[str, object], field: str) -> float:
    """Read a required numeric profile field."""
    value = profile.get(field)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise TypeError(f"profile field {field!r} must be numeric")
    return float(value)


def numbers(profile: Mapping[str, object], field: str, count: int) -> list[float]:
    """Read a fixed-length numeric list profile field."""
    value = profile.get(field)
    if not isinstance(value, list) or len(value) != count:
        raise TypeError(f"profile field {field!r} must contain {count} numbers")
    return [float(item) for item in value]


def string(profile: Mapping[str, object], field: str) -> str:
    """Read a required string profile field."""
    value = profile.get(field)
    if not isinstance(value, str):
        raise TypeError(f"profile field {field!r} must be a string")
    return value


def boolean(profile: Mapping[str, object], field: str) -> bool:
    """Read a required Boolean profile field."""
    value = profile.get(field)
    if not isinstance(value, bool):
        raise TypeError(f"profile field {field!r} must be a Boolean")
    return value
