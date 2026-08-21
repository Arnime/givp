"""Griewank benchmark function."""

from collections.abc import Sequence

import numpy as np
from numpy.typing import NDArray


def griewank(x: NDArray | Sequence[float]) -> float:
    """Evaluate the Griewank function, whose global minimum is at the origin."""
    values = np.asarray(x, dtype=float)
    if values.size == 0:
        return 1.0
    indices = np.arange(1, values.size + 1)
    squared_sum = np.sum(values * values) / 4000.0
    cosine_product = float(np.prod(np.cos(values / np.sqrt(indices))))
    return float(1.0 + squared_sum - cosine_product)
