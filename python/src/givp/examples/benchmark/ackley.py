"""Ackley benchmark function."""

from collections.abc import Sequence

import numpy as np
from numpy.typing import NDArray


def ackley(x: NDArray | Sequence[float]) -> float:
    """Evaluate the Ackley function, whose global minimum is at the origin."""
    values = np.asarray(x, dtype=float)
    if values.size == 0:
        return 0.0
    squared_mean = np.sum(values * values) / values.size
    cosine_mean = np.sum(np.cos(2.0 * np.pi * values)) / values.size
    return float(
        -20.0 * np.exp(-0.2 * np.sqrt(squared_mean)) - np.exp(cosine_mean) + 20.0 + np.e
    )
