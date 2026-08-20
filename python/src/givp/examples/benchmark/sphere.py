"""Sphere benchmark function."""

from collections.abc import Sequence

import numpy as np
from numpy.typing import NDArray


def sphere(x: NDArray | Sequence[float]) -> float:
    """Evaluate the Sphere function, whose global minimum is at the origin."""
    values = np.asarray(x, dtype=float)
    return float(np.sum(values * values))

