# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
"""Create GIVP configurations from Optuna suggestions and saved parameters."""

from __future__ import annotations

import optuna

from givp import GIVPConfig


def _suggest_global_config(
    trial: optuna.trial.Trial,
    *,
    time_limit: float,
) -> GIVPConfig:
    """Suggest parameters for the bounded seven-scenario global search."""
    alpha = trial.suggest_float("alpha", 0.14, 0.32)
    adaptive_alpha = trial.suggest_categorical("adaptive_alpha", [True, False])
    if adaptive_alpha:
        alpha_min = trial.suggest_float("alpha_min", 0.08, alpha)
        alpha_max = trial.suggest_float("alpha_max", alpha, 0.48)
    else:
        alpha_min = alpha
        alpha_max = alpha

    use_elite_pool = trial.suggest_categorical("use_elite_pool", [True, False])
    elite_size = trial.suggest_int("elite_size", 3, 8) if use_elite_pool else 5
    path_relink_frequency = (
        trial.suggest_int("path_relink_frequency", 5, 12) if use_elite_pool else 10
    )
    return GIVPConfig(
        max_iterations=80,
        alpha=alpha,
        adaptive_alpha=adaptive_alpha,
        alpha_min=alpha_min,
        alpha_max=alpha_max,
        vnd_iterations=trial.suggest_int("vnd_iterations", 40, 80),
        ils_iterations=trial.suggest_int("ils_iterations", 5, 12),
        perturbation_strength=trial.suggest_int("perturbation_strength", 6, 20),
        use_elite_pool=use_elite_pool,
        elite_size=elite_size,
        path_relink_frequency=path_relink_frequency,
        num_candidates_per_step=trial.suggest_int("num_candidates_per_step", 6, 18),
        use_cache=True,
        cache_size=12000,
        early_stop_threshold=80,
        use_convergence_monitor=False,
        n_workers=1,
        time_limit=time_limit,
        max_evaluations=15000,
        group_size=24,
    )


def _suggest_config(
    trial: optuna.trial.Trial,
    *,
    max_iter: int,
    time_limit: float,
    max_iter_min: int | None = None,
) -> GIVPConfig:
    """Suggest a GIVP configuration for the hydropower benchmark.

    With ``max_iter_min`` the iteration count is tuned in
    ``[max_iter_min, max_iter]`` (log scale); otherwise it is fixed at
    ``max_iter``. The 15000-evaluation cap stops long runs either way.
    """
    if max_iter_min is not None:
        if not 1 <= max_iter_min <= max_iter:
            raise ValueError("max_iter_min must be between 1 and max_iter")
        max_iter = trial.suggest_int("max_iterations", max_iter_min, max_iter, log=True)
    alpha = trial.suggest_float("alpha", 0.05, 0.30)
    adaptive_alpha = trial.suggest_categorical("adaptive_alpha", [True, False])
    if adaptive_alpha:
        alpha_min = trial.suggest_float("alpha_min", 0.03, max(0.06, alpha * 0.9))
        alpha_max = trial.suggest_float(
            "alpha_max",
            max(alpha * 1.05, alpha_min + 0.01),
            min(0.45, max(alpha * 2.5, alpha_min + 0.15)),
        )
    else:
        alpha_min = alpha
        alpha_max = alpha

    vnd_iterations = trial.suggest_int("vnd_iterations", 8, 80)
    ils_iterations = trial.suggest_int("ils_iterations", 1, 12)
    perturbation_strength = trial.suggest_int("perturbation_strength", 1, 20)

    use_elite_pool = trial.suggest_categorical("use_elite_pool", [True, False])
    elite_size = trial.suggest_int("elite_size", 3, 12) if use_elite_pool else 5
    path_relink_frequency = (
        trial.suggest_int("path_relink_frequency", 3, 20) if use_elite_pool else 10
    )

    early_stop_threshold = trial.suggest_int(
        "early_stop_threshold",
        min(10, max_iter),
        max_iter,
    )
    use_convergence_monitor = trial.suggest_categorical(
        "use_convergence_monitor", [True, False]
    )
    num_candidates_per_step = trial.suggest_int("num_candidates_per_step", 4, 25)

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
        num_candidates_per_step=num_candidates_per_step,
        use_cache=True,
        cache_size=12000,
        early_stop_threshold=early_stop_threshold,
        use_convergence_monitor=use_convergence_monitor,
        n_workers=1,
        time_limit=time_limit,
        max_evaluations=15000,
        group_size=24,
    )


def _config_from_params(
    params: dict[str, object], *, max_iter: int, time_limit: float
) -> GIVPConfig:
    """Rebuild a GIVPConfig from serialized Optuna params."""

    def _float(key: str) -> float:
        value = params[key]
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise TypeError(f"{key!r} must be numeric")
        return float(value)

    def _int(key: str) -> int:
        value = params[key]
        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError(f"{key!r} must be an int")
        return value

    def _bool(key: str) -> bool:
        value = params[key]
        if not isinstance(value, bool):
            raise TypeError(f"{key!r} must be bool")
        return value

    if "max_iterations" in params:
        max_iter = _int("max_iterations")
    alpha = _float("alpha")
    adaptive_alpha = _bool("adaptive_alpha")
    alpha_min = _float("alpha_min") if adaptive_alpha else alpha
    alpha_max = _float("alpha_max") if adaptive_alpha else alpha
    use_elite_pool = _bool("use_elite_pool")
    elite_size = _int("elite_size") if use_elite_pool else 5
    path_relink_frequency = _int("path_relink_frequency") if use_elite_pool else 10
    early_stop_threshold = (
        _int("early_stop_threshold")
        if "early_stop_threshold" in params
        else max_iter
    )
    use_convergence_monitor = (
        _bool("use_convergence_monitor")
        if "use_convergence_monitor" in params
        else False
    )

    return GIVPConfig(
        max_iterations=max_iter,
        alpha=alpha,
        adaptive_alpha=adaptive_alpha,
        alpha_min=alpha_min,
        alpha_max=alpha_max,
        vnd_iterations=_int("vnd_iterations"),
        ils_iterations=_int("ils_iterations"),
        perturbation_strength=_int("perturbation_strength"),
        use_elite_pool=use_elite_pool,
        elite_size=elite_size,
        path_relink_frequency=path_relink_frequency,
        num_candidates_per_step=_int("num_candidates_per_step"),
        use_cache=True,
        cache_size=12000,
        early_stop_threshold=early_stop_threshold,
        use_convergence_monitor=use_convergence_monitor,
        n_workers=1,
        time_limit=time_limit,
        max_evaluations=15000,
        group_size=24,
    )
