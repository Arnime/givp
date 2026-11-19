# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
"""Analyze the paired holdout comparison for global hydropower tuning."""

from __future__ import annotations

import argparse
import csv
import itertools
import json
import math
import random
from collections import defaultdict
from pathlib import Path

import numpy as np

from benchmarks.tuning.hydropower.trials import (
    PRIORITY_SCENARIOS,
    PROTECTED_SCENARIOS,
    _scenario_score,
)

SCENARIOS = (
    "downstream_dominant",
    "dry_stable",
    "dry_variable",
    "flood",
    "typical",
    "upstream_peak",
    "wet_rising",
)
ALGORITHMS = ("DE", "PSO", "UPSO", "GIVP")
COMPARATORS = ("DE", "PSO", "UPSO")
HOLDOUT_SEEDS = tuple(range(49, 59))


def _load_csv(path: Path) -> list[dict[str, str]]:
    """Read a UTF-8 CSV file into row dictionaries."""
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _validate_profile(path: Path) -> None:
    """Require the frozen holdout seeds and equal run budgets in the profile."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("optimizer_seeds") != list(HOLDOUT_SEEDS):
        raise ValueError("validation profile must use optimizer seeds 49 through 58")
    if payload.get("max_evaluations") != 15000:
        raise ValueError(
            "validation profile must cap every algorithm at 15000 evaluations"
        )
    profiles = payload.get("profiles")
    if not isinstance(profiles, dict) or any(
        name not in profiles for name in ALGORITHMS
    ):
        raise ValueError("validation profile must contain DE, PSO, UPSO, and GIVP")
    givp_profile = profiles["GIVP"]
    if (
        not isinstance(givp_profile, dict)
        or givp_profile.get("time_limit_seconds") != 300.0
    ):
        raise ValueError("validation profile must enforce a 300-second limit")


def _holm_adjust(p_values: dict[str, float]) -> dict[str, float]:
    """Return Holm step-down adjusted p-values while preserving input order."""
    ordered = sorted(p_values, key=p_values.__getitem__)
    adjusted: dict[str, float] = {}
    running_max = 0.0
    count = len(ordered)
    for rank, name in enumerate(ordered):
        running_max = max(running_max, (count - rank) * p_values[name])
        adjusted[name] = min(1.0, running_max)
    return {name: adjusted[name] for name in p_values}


def _bootstrap_interval(
    values: list[float], *, resamples: int = 20000, seed: int = 20261116
) -> tuple[float, float]:
    """Compute a percentile interval by resampling whole optimizer-seed blocks."""
    if not values:
        raise ValueError("at least one paired seed block is required")
    generator = random.Random(seed)
    estimates = sorted(
        sum(generator.choice(values) for _ in values) / len(values)
        for _ in range(resamples)
    )
    return estimates[int(0.025 * (resamples - 1))], estimates[
        int(0.975 * (resamples - 1))
    ]


def _sign_flip_p_value(values: list[float]) -> float:
    """Compute an exact two-sided paired sign-flip p-value over seed blocks."""
    observed = abs(float(np.mean(values)))
    exceedances = sum(
        abs(
            sum(sign * value for sign, value in zip(signs, values, strict=True))
            / len(values)
        )
        >= observed - 1e-12
        for signs in itertools.product((-1.0, 1.0), repeat=len(values))
    )
    return float(exceedances / (2 ** len(values)))


def analyze_validation(
    runs_path: Path,
    reference_path: Path,
    profile_path: Path,
) -> dict[str, object]:
    """Analyze normalized paired gaps, seed-block intervals, and Holm tests."""
    _validate_profile(profile_path)
    run_rows = _load_csv(runs_path)
    reference_rows = _load_csv(reference_path)
    task_values: dict[tuple[str, int], dict[str, float]] = defaultdict(dict)
    for row in run_rows:
        scenario = row.get("scenario", "")
        algorithm = row.get("algorithm", "")
        seed = int(row.get("optimizer_seed", "-1"))
        if scenario not in SCENARIOS or algorithm not in ALGORITHMS:
            raise ValueError(f"unexpected validation row: {scenario}, {algorithm}")
        key = (scenario, seed)
        if algorithm in task_values[key]:
            raise ValueError(
                f"duplicate result for {scenario}, seed {seed}, {algorithm}"
            )
        objective = float(row["objective"])
        if not math.isfinite(objective):
            raise ValueError(
                f"non-finite objective for {scenario}, seed {seed}, {algorithm}"
            )
        task_values[key][algorithm] = objective
    expected = {(scenario, seed) for scenario in SCENARIOS for seed in HOLDOUT_SEEDS}
    if set(task_values) != expected:
        raise ValueError(
            "runs CSV must contain exactly the 70 scenario-seed holdout tasks"
        )
    if any(set(task_values[key]) != set(ALGORITHMS) for key in expected):
        raise ValueError("each holdout task must contain DE, PSO, UPSO, and GIVP")

    reference_means: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for row in reference_rows:
        if row.get("scenario") in SCENARIOS and row.get("algorithm") in COMPARATORS:
            objective = float(row["objective"])
            if not math.isfinite(objective):
                raise ValueError("reference CSV contains a non-finite objective")
            reference_means[row["scenario"]][row["algorithm"]].append(objective)
    scales: dict[str, float] = {}
    for scenario in SCENARIOS:
        means = {
            algorithm: float(np.mean(values))
            for algorithm, values in reference_means[scenario].items()
            if values
        }
        if set(means) != set(COMPARATORS):
            raise ValueError(
                f"reference CSV must contain all three competitors for {scenario}"
            )
        scales[scenario] = max(abs(min(means.values())), 1.0)

    seed_blocks: dict[str, list[float]] = {name: [] for name in COMPARATORS}
    scenario_gaps: dict[str, dict[str, list[float]]] = {
        name: {scenario: [] for scenario in SCENARIOS} for name in COMPARATORS
    }
    for seed in HOLDOUT_SEEDS:
        for algorithm in COMPARATORS:
            gaps = {
                scenario: _scenario_score(
                    task_values[(scenario, seed)]["GIVP"], scales[scenario]
                )
                - _scenario_score(
                    task_values[(scenario, seed)][algorithm], scales[scenario]
                )
                for scenario in SCENARIOS
            }
            for scenario, gap in gaps.items():
                scenario_gaps[algorithm][scenario].append(gap)
            priority_mean = float(np.mean([gaps[name] for name in PRIORITY_SCENARIOS]))
            protected_mean = float(
                np.mean([gaps[name] for name in PROTECTED_SCENARIOS])
            )
            seed_blocks[algorithm].append(0.5 * (priority_mean + protected_mean))

    raw_p_values = {
        algorithm: _sign_flip_p_value(values)
        for algorithm, values in seed_blocks.items()
    }
    adjusted_p_values = _holm_adjust(raw_p_values)
    comparisons: dict[str, object] = {}
    for algorithm in COMPARATORS:
        values = seed_blocks[algorithm]
        low, high = _bootstrap_interval(values)
        scenario_means = {
            scenario: float(np.mean(scenario_gaps[algorithm][scenario]))
            for scenario in SCENARIOS
        }
        no_large_scenario_regression = all(
            value <= 0.05 for value in scenario_means.values()
        )
        comparisons[algorithm] = {
            "mean_weighted_normalized_gap": float(np.mean(values)),
            "seed_block_bootstrap_95pct_ci": [low, high],
            "paired_sign_flip_p_value": raw_p_values[algorithm],
            "holm_adjusted_p_value": adjusted_p_values[algorithm],
            "scenario_mean_normalized_gaps": scenario_means,
            "no_scenario_regression_over_0_05": no_large_scenario_regression,
            "superiority_supported": (
                high < 0.0
                and adjusted_p_values[algorithm] < 0.05
                and no_large_scenario_regression
            ),
        }
    return {
        "holdout_seeds": list(HOLDOUT_SEEDS),
        "scenarios": list(SCENARIOS),
        "normalization_scales": scales,
        "confidence_method": "20,000 percentile bootstrap resamples of complete seed blocks",
        "hypothesis_test": "exact two-sided sign-flip test over weighted seed-block gaps",
        "holm_family": list(COMPARATORS),
        "comparisons": comparisons,
    }


def main(argv: list[str] | None = None) -> int:
    """Analyze a completed holdout campaign and write a JSON report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--reference-runs", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = analyze_validation(args.runs, args.reference_runs, args.profile)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
