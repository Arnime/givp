# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
"""Objective construction for hyperparameter tuning."""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import optuna

from benchmarks.common.problems import PROBLEM_REGISTRY
from benchmarks.tuning.search import _suggest_config
from givp import GIVPConfig, givp


def build_objective(
    functions: list[str],
    dims: int,
    n_eval_seeds: int,
    max_iter: int,
    time_limit: float,
) -> Callable[[optuna.trial.Trial], float]:
    """Return an Optuna objective callable.

    The objective averages ``result.fun`` over all (function, seed) pairs.
    To avoid scale dominance, each function's result is divided by the
    reference value obtained by GIVP-full with seed=0 on the first call
    (cached after the first trial that evaluates it).

    Parameters
    ----------
    functions:
        Names from PROBLEM_REGISTRY to include in the objective.
    dims:
        Problem dimensionality.
    n_eval_seeds:
        Number of independent seeds per function per trial.
    max_iter:
        Maximum GIVP iterations.
    time_limit:
        Per-run wall-clock budget in seconds.

    Returns
    -------
    callable
        An ``objective(trial) -> float`` function for Optuna.
    """
    eval_seeds = list(range(n_eval_seeds))

    # Reference scale per function: computed once using GIVP-full seed=0.
    # This normalises across functions so no single function dominates.
    reference_scale: dict[str, float] = {}

    def _get_scale(fn_name: str) -> float:
        if fn_name in reference_scale:
            return reference_scale[fn_name]
        spec = PROBLEM_REGISTRY[fn_name]
        bounds = spec["bounds_factory"](dims)
        ref_cfg = GIVPConfig(
            max_iterations=max_iter,
            alpha=0.12,
            adaptive_alpha=True,
            vnd_iterations=100,
            ils_iterations=5,
            time_limit=time_limit,
        )
        ref = givp(spec["func"], bounds, config=ref_cfg, seed=0)
        scale = max(abs(float(ref.fun)), 1e-12)
        reference_scale[fn_name] = scale
        return scale

    def objective(trial: optuna.trial.Trial) -> float:
        """Optuna objective: mean normalised best value over all (fn, seed) pairs."""
        cfg = _suggest_config(trial, max_iter, time_limit)
        scores: list[float] = []

        for fn_name in functions:
            spec = PROBLEM_REGISTRY[fn_name]
            bounds = spec["bounds_factory"](dims)
            scale = _get_scale(fn_name)

            for seed in eval_seeds:
                res = givp(spec["func"], bounds, config=cfg, seed=seed)
                scores.append(float(res.fun) / scale)

        return float(np.mean(scores))

    return objective
