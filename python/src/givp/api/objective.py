# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
"""Objective adaptation for the minimization-oriented optimization core."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from givp.api.types import ObjectiveFn
from givp.exceptions import EvaluationLimitReached


@dataclass
class ObjectiveState:
    """Mutable evaluation counter and incumbent shared with the public API."""

    cost: float = float("inf")
    solution: np.ndarray | None = None


def _wrap_objective(
    func: ObjectiveFn,
    direction: str,
    counter: list[int],
    max_evaluations: int = 0,
    incumbent: ObjectiveState | None = None,
) -> ObjectiveFn:
    """Normalize objective direction, count evaluations and reject invalid values."""
    if direction not in ("minimize", "maximize"):
        raise ValueError("direction must be 'minimize' or 'maximize'")
    sign = -1.0 if direction == "maximize" else 1.0

    def wrapped(x: np.ndarray) -> float:
        if max_evaluations > 0 and counter[0] >= max_evaluations:
            raise EvaluationLimitReached("evaluation limit reached")
        counter[0] += 1
        try:
            value = float(func(np.asarray(x, dtype=float)))
        except (ValueError, RuntimeError, FloatingPointError):
            return float("inf")
        if not np.isfinite(value):
            return float("inf")
        normalized = sign * value
        if incumbent is not None and normalized < incumbent.cost:
            incumbent.cost = normalized
            incumbent.solution = np.asarray(x, dtype=float).copy()
        return normalized

    return wrapped
