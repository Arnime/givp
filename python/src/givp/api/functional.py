# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
"""SciPy-style functional entry point for GIVP."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from givp.api.objective import _wrap_objective
from givp.api.types import BoundsLike, IterationCallback, ObjectiveFn
from givp.api.validation import (
    _normalize_bounds,
    _normalize_initial_guesses,
    _resolve_direction,
)
from givp.config import GIVPConfig
from givp.core import grasp_ils_vnd
from givp.core.helpers import _set_seed
from givp.result import AlgorithmMeta, OptimizeResult, TerminationReason


def givp(
    func: ObjectiveFn,
    bounds: BoundsLike,
    *,
    num_vars: int | None = None,
    minimize: bool | None = None,
    direction: str | None = None,
    config: GIVPConfig | None = None,
    initial_guess: Sequence[float] | None = None,
    initial_guesses: Sequence[Sequence[float]] | None = None,
    iteration_callback: IterationCallback | None = None,
    seed: int | None = None,
    verbose: bool = False,
) -> OptimizeResult:
    """Minimize or maximize a scalar function with GRASP-ILS-VND-PR."""
    resolved_direction = _resolve_direction(minimize, direction)
    cfg = config or GIVPConfig()
    cfg = GIVPConfig(**{**cfg.__dict__, "minimize": resolved_direction == "minimize"})

    _set_seed(seed)
    lower, upper, inferred_num_vars = _normalize_bounds(bounds, num_vars)
    warm_start_guesses = _normalize_initial_guesses(
        initial_guess,
        initial_guesses,
        lower,
        upper,
        inferred_num_vars,
    )

    if cfg.integer_split is None:
        cfg = GIVPConfig(**{**cfg.__dict__, "integer_split": inferred_num_vars})
    nfev_counter = [0]
    wrapped = _wrap_objective(func, resolved_direction, nfev_counter)

    solution, core_value, actual_nit, termination_message = grasp_ils_vnd(
        wrapped,
        inferred_num_vars,
        cfg,
        verbose=verbose,
        iteration_callback=iteration_callback,
        lower=lower,
        upper=upper,
        initial_guesses=warm_start_guesses,
    )

    x = np.asarray(solution, dtype=float)
    sign = -1.0 if resolved_direction == "maximize" else 1.0
    fun_value = sign * float(core_value)
    success = np.isfinite(fun_value)
    return OptimizeResult(
        x=x,
        fun=fun_value,
        nit=actual_nit,
        nfev=nfev_counter[0],
        success=success,
        message=(termination_message if success else "no finite solution found"),
        direction=resolved_direction,
        meta=AlgorithmMeta(
            termination_reason=TerminationReason.from_message(
                termination_message
            ).value,
            max_iterations=cfg.max_iterations,
            n_vars=inferred_num_vars,
        ),
    )
