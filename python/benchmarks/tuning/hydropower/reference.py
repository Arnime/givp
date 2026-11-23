# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
"""Load campaign references and prior Optuna configurations."""

from __future__ import annotations

import csv
import json
from collections.abc import Sequence
from pathlib import Path
from typing import cast

import numpy as np


def _load_de_reference(path: Path | None, scenarios: Sequence[str]) -> dict[str, float]:
    """Load mean DE objectives used to put scenarios on a common scale."""
    return _load_reference([path] if path is not None else [], scenarios, ("DE",))[0]


def _load_reference(
    paths: Sequence[Path],
    scenarios: Sequence[str],
    algorithms: Sequence[str],
) -> tuple[dict[str, float], dict[str, str]]:
    """Return each scenario's best mean objective and winning algorithm."""
    if not paths:
        return {scenario: 0.0 for scenario in scenarios}, {}
    values: dict[tuple[str, str], list[float]] = {}
    for path in paths:
        with path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                scenario = row.get("scenario")
                algorithm = row.get("algorithm")
                if scenario in scenarios and algorithm in algorithms:
                    key = (cast(str, scenario), cast(str, algorithm))
                    values.setdefault(key, []).append(float(row["objective"]))
    reference: dict[str, float] = {}
    winners: dict[str, str] = {}
    for scenario in scenarios:
        means = {
            algorithm: float(np.mean(values[(scenario, algorithm)]))
            for algorithm in algorithms
            if (scenario, algorithm) in values
        }
        if not means:
            raise ValueError(f"reference has no {list(algorithms)} rows for {scenario}")
        winners[scenario] = min(means, key=means.__getitem__)
        reference[scenario] = means[winners[scenario]]
    return reference, winners


def _load_seed_configs(paths: Sequence[Path]) -> list[dict[str, object]]:
    """Read prior Optuna params or archived GIVP profiles as startup trials."""
    tunable_params = {
        "alpha",
        "adaptive_alpha",
        "alpha_min",
        "alpha_max",
        "vnd_iterations",
        "ils_iterations",
        "perturbation_strength",
        "use_elite_pool",
        "elite_size",
        "path_relink_frequency",
        "early_stop_threshold",
        "use_convergence_monitor",
        "num_candidates_per_step",
    }
    required_params = {
        "alpha",
        "adaptive_alpha",
        "vnd_iterations",
        "ils_iterations",
        "perturbation_strength",
        "use_elite_pool",
        "early_stop_threshold",
        "use_convergence_monitor",
        "num_candidates_per_step",
    }
    configs: list[dict[str, object]] = []
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        params = payload.get("best_trial_params")
        if not isinstance(params, dict):
            profiles = payload.get("profiles")
            params = profiles.get("GIVP") if isinstance(profiles, dict) else None
        if not isinstance(params, dict):
            raise ValueError(f"{path} has neither best_trial_params nor profiles.GIVP")
        config = {
            str(key): value for key, value in params.items() if key in tunable_params
        }
        missing = sorted(required_params - config.keys())
        if missing:
            raise ValueError(
                f"{path} is missing tunable parameters: {', '.join(missing)}"
            )
        adaptive_alpha = config["adaptive_alpha"]
        if not isinstance(adaptive_alpha, bool):
            raise ValueError(f"{path} adaptive_alpha must be bool")
        if adaptive_alpha:
            for key in ("alpha_min", "alpha_max"):
                if key not in config:
                    raise ValueError(f"{path} is missing {key} for adaptive_alpha")
        else:
            config.pop("alpha_min", None)
            config.pop("alpha_max", None)
        use_elite_pool = config["use_elite_pool"]
        if not isinstance(use_elite_pool, bool):
            raise ValueError(f"{path} use_elite_pool must be bool")
        if use_elite_pool:
            for key in ("elite_size", "path_relink_frequency"):
                if key not in config:
                    raise ValueError(f"{path} is missing {key} for use_elite_pool")
        else:
            config.pop("elite_size", None)
            config.pop("path_relink_frequency", None)
        configs.append(config)
    return configs
