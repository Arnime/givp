"""Schwefel benchmark function."""

from collections.abc import Sequence

import numpy as np
from numpy.typing import NDArray


def schwefel(x: NDArray | Sequence[float]) -> float:
    """Evaluate the classic Schwefel function."""
    values = np.asarray(x, dtype=float)
    return float(
        418.9829 * values.size - np.sum(values * np.sin(np.sqrt(np.abs(values))))
    )
