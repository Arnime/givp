"""Restricted Candidate List selection strategies."""

import numpy as np


def select_rcl(
    valid_indices: np.ndarray, valid_ratios: np.ndarray, alpha: float
) -> np.ndarray:
    """Build a ratio-based Restricted Candidate List."""
    threshold = valid_ratios.max() - alpha * (
        valid_ratios.max() - valid_ratios.min()
    )
    rcl_indices = valid_indices[valid_ratios >= threshold]
    if len(rcl_indices) == 0:
        n_top = max(1, int(len(valid_indices) * 0.3))
        top_idx = np.argpartition(valid_ratios, -n_top)[-n_top:]
        rcl_indices = valid_indices[top_idx]
    return np.asarray(rcl_indices)


def _select_from_rcl(
    costs: np.ndarray, alpha: float, rng: np.random.Generator
) -> int | None:
    """Select one finite candidate through a cost-based RCL."""
    valid_mask = np.isfinite(costs)
    if not np.any(valid_mask):
        return None
    valid_idx = np.nonzero(valid_mask)[0]
    valid_costs = costs[valid_idx]
    threshold = valid_costs.min() + alpha * (
        valid_costs.max() - valid_costs.min()
    )
    rcl_local = valid_idx[valid_costs <= threshold]
    if rcl_local.size == 0:
        rcl_local = valid_idx
    return int(rng.choice(rcl_local))
