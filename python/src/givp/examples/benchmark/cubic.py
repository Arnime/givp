"""Constrained cubic benchmark encoded with an external penalty."""

from collections.abc import Sequence

from numpy.typing import NDArray


def constrained_cubic(x: NDArray | Sequence[float]) -> float:
    """Evaluate a synthetic constrained cubic problem inspired by G06."""
    x1, x2 = float(x[0]), float(x[1])
    objective = (x1 - 10.0) ** 3 + (x2 - 20.0) ** 3
    violation_1 = max(0.0, -((x1 - 5.0) ** 2) - (x2 - 5.0) ** 2 + 100.0)
    violation_2 = max(0.0, (x1 - 6.0) ** 2 + (x2 - 5.0) ** 2 - 82.81)
    return float(
        objective + 1e6 * (violation_1 * violation_1 + violation_2 * violation_2)
    )
