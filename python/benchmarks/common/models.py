# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
"""Shared benchmark result contracts."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypedDict

from numpy.typing import NDArray

Objective = Callable[[NDArray], float]


class ProblemSpec(TypedDict):
    """Definition of a continuous benchmark problem."""

    func: Objective
    bounds_factory: Callable[[int], list[tuple[float, float]]]
    optimum: float
    reference: str
