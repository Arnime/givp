"""Random-keys quadratic-assignment benchmark objective."""

from collections.abc import Sequence

import numpy as np
from numpy.typing import NDArray


def qap_cost(x: NDArray | Sequence[float], flow: NDArray, distance: NDArray) -> float:
    """Evaluate a QAP solution encoded as a random-keys vector."""
    permutation = np.argsort(np.asarray(x))
    permuted_distance = np.asarray(distance)[np.ix_(permutation, permutation)]
    return float(np.sum(np.asarray(flow) * permuted_distance))
