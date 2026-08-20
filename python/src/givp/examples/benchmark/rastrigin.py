"""Rastrigin benchmark function."""

from collections.abc import Sequence

import numpy as np
from numpy.typing import NDArray


def rastrigin(x: NDArray | Sequence[float]) -> float:
    """Evaluate the multimodal Rastrigin function."""
    values = np.asarray(x, dtype=float)
    return float(
        10.0 * values.size
        + np.sum(values * values - 10.0 * np.cos(2.0 * np.pi * values))
    )
