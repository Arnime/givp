# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
"""Objective adaptation for the minimization-oriented optimization core."""

from __future__ import annotations

import numpy as np

from givp.api.types import ObjectiveFn


def _wrap_objective(
    func: ObjectiveFn, direction: str, counter: list[int]
) -> ObjectiveFn:
    """Normalize objective direction, count evaluations and reject invalid values."""
    if direction not in ("minimize", "maximize"):
        raise ValueError("direction must be 'minimize' or 'maximize'")
    sign = -1.0 if direction == "maximize" else 1.0

    def wrapped(x: np.ndarray) -> float:
        counter[0] += 1
        try:
            value = float(func(np.asarray(x, dtype=float)))
        except (ValueError, RuntimeError, FloatingPointError):
            return float("inf")
        if not np.isfinite(value):
            return float("inf")
        return sign * value

    return wrapped
