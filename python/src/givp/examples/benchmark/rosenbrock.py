"""Rosenbrock benchmark function."""

from collections.abc import Sequence

import numpy as np
from numpy.typing import NDArray


def rosenbrock(x: NDArray | Sequence[float]) -> float:
    """Evaluate the Rosenbrock function, whose minimum is the all-ones vector."""
    values = np.asarray(x, dtype=float)
    if values.size < 2:
        return 0.0
    return float(
        np.sum(100.0 * (values[1:] - values[:-1] ** 2) ** 2 + (1.0 - values[:-1]) ** 2)
    )
