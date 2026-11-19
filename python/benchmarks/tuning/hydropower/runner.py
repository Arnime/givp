# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
"""Run single-scenario Optuna tuning for synthetic hydropower."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import optuna
import optuna.logging as optuna_logging

from benchmarks.comparison.hydropower.campaign import (
    _load_benchmark,
    _optimization_definition,
)
from benchmarks.tuning.hydropower.config import _config_from_params
from benchmarks.tuning.hydropower.trials import _run_single_trial


def run_tuning(
    benchmark_root: Path,
    *,
    scenario: str,
    n_trials: int,
    n_eval_seeds: int,
    sampler_seed: int,
    max_iter: int,
    time_limit: float,
    study_name: str,
    storage: str | None,
    verbose: bool,
) -> dict[str, object]:
    """Run Optuna tuning for the hydropower benchmark."""
    if not verbose:
        optuna_logging.set_verbosity(optuna_logging.WARNING)

    benchmark = _load_benchmark(benchmark_root)
    scenario_definition = next(
        item for item in benchmark.scenarios if item.definition.name == scenario
    )
    profile = {
        "max_iterations": max_iter,
        "alpha": 0.17,
        "vnd_iterations": 25,
        "ils_iterations": 5,
        "perturbation_strength": 10,
        "use_elite_pool": True,
        "elite_size": 5,
        "path_relink_frequency": 8,
        "num_candidates_per_step": 20,
        "use_cache": True,
        "cache_size": 12000,
        "early_stop_threshold": 48,
        "use_convergence_monitor": True,
        "n_workers": 1,
    }
    definition = _optimization_definition(
        benchmark.cascade, scenario_definition, profile
    )
    study = optuna.create_study(
        study_name=study_name,
        direction="minimize",
        sampler=optuna.samplers.TPESampler(seed=sampler_seed),
        storage=storage,
        load_if_exists=True,
    )

    def objective(trial: optuna.trial.Trial) -> float:
        return _run_single_trial(
            trial,
            definition,
            n_eval_seeds=n_eval_seeds,
            max_iter=max_iter,
            time_limit=time_limit,
        )

    study.optimize(objective, n_trials=n_trials, show_progress_bar=verbose)
    best_trial = study.best_trial
    best_config = _config_from_params(
        dict(best_trial.params), max_iter=max_iter, time_limit=time_limit
    )
    best_params = {
        field.name: getattr(best_config, field.name)
        for field in dataclasses.fields(best_config)
    }
    return {
        "metadata": {
            "scenario": scenario,
            "n_trials": n_trials,
            "n_completed_trials": len(study.trials),
            "n_eval_seeds": n_eval_seeds,
            "sampler": "TPESampler",
            "sampler_seed": sampler_seed,
            "max_iter": max_iter,
            "time_limit": time_limit,
            "best_trial_number": best_trial.number,
            "best_value": best_trial.value,
            "benchmark_root": str(benchmark_root),
        },
        "best_trial_params": dict(best_trial.params),
        "best_params": best_params,
    }
