"""Layout and correlated perturbations for structured VND neighborhoods."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from givp.core.helpers import (
    _get_continuous_move_scales,
    _get_group_size,
    _get_half,
)


@dataclass(frozen=True)
class GroupLayout:
    """Structured continuous groups with an optional paired integer tail."""

    continuous_size: int
    n_groups: int
    n_steps: int
    paired_integer: bool


def _group_layout(num_vars: int) -> GroupLayout | None:
    """Infer continuous groups for fully continuous or paired mixed vectors."""
    split = _get_half(num_vars)
    if split <= 0:
        return None
    n_steps = _get_group_size()
    if n_steps is None or n_steps < 1:
        return None
    paired_integer = split < num_vars
    if paired_integer and num_vars - split != split:
        return None
    n_groups = split // n_steps
    if n_groups < 1 or n_groups * n_steps != split:
        return None
    return GroupLayout(split, n_groups, n_steps, paired_integer)


def _sign_from_delta(delta: float) -> int:
    """Return discrete direction sign from continuous delta."""
    if delta > 0:
        return 1
    if delta < 0:
        return -1
    return 0


def _apply_group_perturbation(
    solution: np.ndarray,
    old_cont: np.ndarray,
    old_int: np.ndarray | None,
    start: int,
    half: int,
    n_steps: int,
    lower_arr: np.ndarray,
    upper_arr: np.ndarray,
    rng: np.random.Generator,
) -> None:
    """Apply a correlated perturbation to all steps of one group."""
    end = start + n_steps
    span = upper_arr[start:end] - lower_arr[start:end]
    scale = float(rng.choice(np.asarray(_get_continuous_move_scales())))
    base_delta = rng.uniform(-scale, scale)
    noise = rng.uniform(-0.4 * scale, 0.4 * scale, size=n_steps)
    solution[start:end] = np.clip(
        old_cont + (base_delta + noise) * span,
        lower_arr[start:end],
        upper_arr[start:end],
    )
    if old_int is None:
        return
    delta_int = _sign_from_delta(base_delta)
    int_start = half + start
    for step_idx in range(n_steps):
        lo = int(np.ceil(lower_arr[int_start + step_idx]))
        hi = int(np.floor(upper_arr[int_start + step_idx]))
        new_val = int(np.rint(old_int[step_idx])) + delta_int
        solution[int_start + step_idx] = float(np.clip(new_val, lo, hi))


def _apply_block_perturbation(
    solution: np.ndarray,
    old_vals: np.ndarray,
    half: int,
    n_groups: int,
    n_steps: int,
    block_start: int,
    block_end: int,
    lower_arr: np.ndarray,
    upper_arr: np.ndarray,
    base_delta: float,
    paired_integer: bool = True,
) -> None:
    """Apply a coordinated perturbation to a step block across all groups."""
    int_delta = _sign_from_delta(base_delta)
    for group_idx in range(n_groups):
        offset = group_idx * n_steps
        for step_idx in range(block_start, block_end):
            cont_idx = offset + step_idx
            span = upper_arr[cont_idx] - lower_arr[cont_idx]
            solution[cont_idx] = float(
                np.clip(
                    old_vals[cont_idx] + base_delta * span,
                    lower_arr[cont_idx],
                    upper_arr[cont_idx],
                )
            )
            if paired_integer:
                int_idx = half + cont_idx
                lo = int(np.ceil(lower_arr[int_idx]))
                hi = int(np.floor(upper_arr[int_idx]))
                solution[int_idx] = float(
                    np.clip(int(np.rint(old_vals[int_idx])) + int_delta, lo, hi)
                )
