"""Exact and penalty-based formulations of the knapsack benchmark."""

from collections.abc import Sequence

import numpy as np
from numpy.typing import NDArray


def knapsack_dp(
    values: Sequence[int], weights: Sequence[int], capacity: int
) -> tuple[int, NDArray]:
    """Return the exact value and selection for a 0/1 knapsack instance."""
    item_values = np.asarray(values, dtype=int)
    item_weights = np.asarray(weights, dtype=int)
    item_count = int(item_values.size)
    table = np.zeros((item_count + 1, capacity + 1), dtype=int)

    for item in range(1, item_count + 1):
        weight = int(item_weights[item - 1])
        value = int(item_values[item - 1])
        for remaining_capacity in range(capacity + 1):
            table[item, remaining_capacity] = table[item - 1, remaining_capacity]
            if weight <= remaining_capacity:
                candidate = table[item - 1, remaining_capacity - weight] + value
                if candidate > table[item, remaining_capacity]:
                    table[item, remaining_capacity] = candidate

    selection = np.zeros(item_count, dtype=int)
    remaining_capacity = capacity
    for item in range(item_count, 0, -1):
        if table[item, remaining_capacity] != table[item - 1, remaining_capacity]:
            selection[item - 1] = 1
            remaining_capacity -= int(item_weights[item - 1])
    return int(table[item_count, capacity]), selection


def knapsack_penalty(
    x: NDArray | Sequence[float],
    values: Sequence[int],
    weights: Sequence[int],
    capacity: int,
    overflow_penalty: float = 1000.0,
) -> float:
    """Evaluate a thresholded knapsack selection with overflow penalty."""
    selection = (np.asarray(x, dtype=float) > 0.5).astype(int)
    total_value = float(np.sum(selection * np.asarray(values)))
    total_weight = float(np.sum(selection * np.asarray(weights)))
    overflow = max(0.0, total_weight - capacity)
    return float(-total_value + overflow_penalty * overflow)
