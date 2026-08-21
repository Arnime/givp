# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
"""Optuna study execution and result persistence."""

from __future__ import annotations

import dataclasses
import logging
import time

import optuna
import optuna.logging as optuna_logging

import givp
from benchmarks.tuning.objective import build_objective
from benchmarks.tuning.search import _config_from_params

_GIVP_VERSION = getattr(givp, "__version__", "unknown")
_log = logging.getLogger(__name__)


def run_tuning(
    functions: list[str],
    dims: int,
    n_trials: int,
    n_eval_seeds: int,
    sampler_seed: int,
    max_iter: int,
    time_limit: float,
    study_name: str,
    storage: str | None,
    verbose: bool,
) -> dict:
    """Run the Optuna hyperparameter search.

    Parameters
    ----------
    functions:
        Benchmark functions to evaluate in each trial.
    dims:
        Problem dimensionality.
    n_trials:
        Number of Optuna trials.
    n_eval_seeds:
        Seeds per (trial, function) pair.  Higher = more stable estimate,
        but slower.  3 is usually sufficient.
    sampler_seed:
        Seed for the TPE sampler, ensuring reproducible trial ordering.
    max_iter:
        Fixed max iterations for GIVP inside each trial.
    time_limit:
        Per-run wall-clock cap in seconds inside each trial.
    study_name:
        Optuna study name (used for storage and display).
    storage:
        Optuna storage URL (e.g. ``sqlite:///tune.db``).  Pass ``None``
        for in-memory (default, not persistent across crashes).
    verbose:
        If True, show Optuna's INFO logs; otherwise show only warnings.

    Returns
    -------
    dict
        Result payload with keys ``metadata`` and ``best_params``.
    """
    if not verbose:
        optuna_logging.set_verbosity(optuna_logging.WARNING)

    sampler = optuna.samplers.TPESampler(seed=sampler_seed)
    study = optuna.create_study(
        study_name=study_name,
        direction="minimize",
        sampler=sampler,
        storage=storage,
        load_if_exists=True,
    )

    objective = build_objective(functions, dims, n_eval_seeds, max_iter, time_limit)

    _log.info("Starting Optuna study: %r", study_name)
    _log.info(
        "  %d trials x %d function(s) x %d seed(s) each",
        n_trials,
        len(functions),
        n_eval_seeds,
    )
    _log.info(
        "  sampler: TPE (seed=%d)  storage: %s", sampler_seed, storage or "in-memory"
    )
    _log.info("")

    t0 = time.perf_counter()
    study.optimize(
        objective,
        n_trials=n_trials,
        show_progress_bar=verbose,
    )
    elapsed = time.perf_counter() - t0

    best_trial = study.best_trial
    _log.info("\nBest trial: #%d  value=%.6f", best_trial.number, best_trial.value)
    _log.info("Duration: %.1fs", elapsed)

    # Reconstruct the full GIVPConfig from the best trial params.
    # `best_trial` is a FrozenTrial (not a suggest-capable Trial).
    best_cfg = _config_from_params(dict(best_trial.params), max_iter, time_limit)

    # Serialise GIVPConfig to a plain dict (dataclass)

    best_params = {
        f.name: getattr(best_cfg, f.name) for f in dataclasses.fields(best_cfg)
    }

    return {
        "metadata": {
            "givp_version": _GIVP_VERSION,
            "study_name": study_name,
            "n_trials": n_trials,
            "n_completed_trials": len(study.trials),
            "sampler": "TPESampler",
            "sampler_seed": sampler_seed,
            "dims": dims,
            "functions": functions,
            "n_eval_seeds": n_eval_seeds,
            "max_iter": max_iter,
            "time_limit_per_run": time_limit,
            "best_trial_number": best_trial.number,
            "best_value": best_trial.value,
            "duration_s": round(elapsed, 2),
        },
        "best_params": best_params,
        "best_trial_params": dict(best_trial.params),
    }
