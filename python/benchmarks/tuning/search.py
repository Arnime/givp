# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
"""Optuna search-space definitions."""

from __future__ import annotations

from collections.abc import Mapping

import optuna

from givp import GIVPConfig


def _suggest_config(
    trial: optuna.trial.Trial, max_iter: int, time_limit: float
) -> GIVPConfig:
    """Map an Optuna trial to a GIVPConfig.

    Parameters
    ----------
    trial:
        Optuna Trial object.
    max_iter:
        Fixed maximum iterations (passed from CLI, not tuned).
    time_limit:
        Per-run wall-clock limit in seconds (passed from CLI, not tuned).

    Returns
    -------
    GIVPConfig
        Configuration built from the trial's suggested hyperparameters.
    """
    alpha = trial.suggest_float("alpha", 0.05, 0.30)
    adaptive_alpha = trial.suggest_categorical("adaptive_alpha", [True, False])

    if adaptive_alpha:
        alpha_min = trial.suggest_float("alpha_min", 0.03, alpha * 0.9)
        alpha_max = trial.suggest_float(
            "alpha_max", alpha * 1.1, min(0.45, alpha * 3.0)
        )
    else:
        alpha_min = alpha
        alpha_max = alpha

    vnd_iterations = trial.suggest_int("vnd_iterations", 20, 500)
    ils_iterations = trial.suggest_int("ils_iterations", 1, 20)
    perturbation_strength = trial.suggest_int("perturbation_strength", 1, 8)

    use_elite_pool = trial.suggest_categorical("use_elite_pool", [True, False])
    elite_size = trial.suggest_int("elite_size", 3, 15) if use_elite_pool else 5
    path_relink_frequency = (
        trial.suggest_int("path_relink_frequency", 3, 25) if use_elite_pool else 10
    )

    early_stop_threshold = trial.suggest_int(
        "early_stop_threshold", min(10, max_iter), max_iter
    )
    use_convergence_monitor = trial.suggest_categorical(
        "use_convergence_monitor", [True, False]
    )

    return GIVPConfig(
        max_iterations=max_iter,
        alpha=alpha,
        adaptive_alpha=adaptive_alpha,
        alpha_min=alpha_min,
        alpha_max=alpha_max,
        vnd_iterations=vnd_iterations,
        ils_iterations=ils_iterations,
        perturbation_strength=perturbation_strength,
        use_elite_pool=use_elite_pool,
        elite_size=elite_size,
        path_relink_frequency=path_relink_frequency,
        use_cache=True,
        cache_size=10_000,
        early_stop_threshold=early_stop_threshold,
        use_convergence_monitor=use_convergence_monitor,
        time_limit=time_limit,
    )


def _config_from_params(
    params: Mapping[str, object], max_iter: int, time_limit: float
) -> GIVPConfig:
    """Build ``GIVPConfig`` from Optuna params exported by a completed trial."""

    def _as_float(key: str) -> float:
        value = params[key]
        if isinstance(value, bool):
            raise TypeError(f"{key!r} must be float, got bool")
        if not isinstance(value, (int, float)):
            raise TypeError(f"{key!r} must be numeric, got {type(value).__name__}")
        return float(value)

    def _as_int(key: str) -> int:
        value = params[key]
        if isinstance(value, bool):
            raise TypeError(f"{key!r} must be int, got bool")
        if not isinstance(value, int):
            raise TypeError(f"{key!r} must be int, got {type(value).__name__}")
        return value

    def _as_bool(key: str) -> bool:
        value = params[key]
        if not isinstance(value, bool):
            raise TypeError(f"{key!r} must be bool, got {type(value).__name__}")
        return value

    alpha = _as_float("alpha")
    adaptive_alpha = _as_bool("adaptive_alpha")

    if adaptive_alpha:
        alpha_min = _as_float("alpha_min")
        alpha_max = _as_float("alpha_max")
    else:
        alpha_min = alpha
        alpha_max = alpha

    vnd_iterations = _as_int("vnd_iterations")
    ils_iterations = _as_int("ils_iterations")
    perturbation_strength = _as_int("perturbation_strength")

    use_elite_pool = _as_bool("use_elite_pool")
    elite_size = _as_int("elite_size") if use_elite_pool else 5
    path_relink_frequency = _as_int("path_relink_frequency") if use_elite_pool else 10

    early_stop_threshold = _as_int("early_stop_threshold")
    use_convergence_monitor = _as_bool("use_convergence_monitor")

    return GIVPConfig(
        max_iterations=max_iter,
        alpha=alpha,
        adaptive_alpha=adaptive_alpha,
        alpha_min=alpha_min,
        alpha_max=alpha_max,
        vnd_iterations=vnd_iterations,
        ils_iterations=ils_iterations,
        perturbation_strength=perturbation_strength,
        use_elite_pool=use_elite_pool,
        elite_size=elite_size,
        path_relink_frequency=path_relink_frequency,
        use_cache=True,
        cache_size=10_000,
        early_stop_threshold=early_stop_threshold,
        use_convergence_monitor=use_convergence_monitor,
        time_limit=time_limit,
    )
