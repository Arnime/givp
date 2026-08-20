# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
"""Shared type definitions for the public Python API."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Literal

import numpy as np
from numpy.typing import NDArray

BoundsLike = Sequence[tuple[float, float]] | tuple[Sequence[float], Sequence[float]]
Direction = Literal["minimize", "maximize"]
ObjectiveFn = Callable[[NDArray[np.float64]], float]
IterationCallback = Callable[[int, float, NDArray[np.float64]], None]
