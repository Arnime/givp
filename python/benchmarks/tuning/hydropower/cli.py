# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
"""Command-line entry point for single-scenario hydropower tuning."""

from __future__ import annotations

import argparse
import json
import logging
from collections.abc import Mapping
from pathlib import Path
from typing import cast

from benchmarks.tuning.hydropower.runner import run_tuning

_log = logging.getLogger(__name__)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Tune GIVP hyperparameters for one synthetic hydropower scenario using Optuna.",
    )
    parser.add_argument(
        "--benchmark-root",
        type=Path,
        required=True,
        help="Path to experiments/synthetic_hydropower/benchmarks/v1.0.0",
    )
    parser.add_argument(
        "--scenario",
        type=str,
        default="typical",
        help="Scenario name to optimize (default: typical).",
    )
    parser.add_argument(
        "--n-trials", type=int, default=60, help="Number of Optuna trials."
    )
    parser.add_argument(
        "--n-eval-seeds",
        type=int,
        default=3,
        help="Number of seeds used per trial to estimate objective value.",
    )
    parser.add_argument(
        "--max-iter",
        type=int,
        default=80,
        help="Maximum GIVP iterations per evaluation.",
    )
    parser.add_argument(
        "--time-limit",
        type=float,
        default=300.0,
        help="Per-run wall-clock budget in seconds.",
    )
    parser.add_argument(
        "--sampler-seed",
        type=int,
        default=42,
        help="Random seed for the TPE sampler.",
    )
    parser.add_argument(
        "--study-name",
        type=str,
        default=None,
        help="Optional study name for Optuna storage.",
    )
    parser.add_argument(
        "--storage",
        type=str,
        default=None,
        help="Optional Optuna storage URL, e.g. sqlite:///givp_hydropower_tuning.db",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("best_hydropower_config.json"),
        help="Path for the JSON payload of the best config.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show Optuna progress logs.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run single-scenario hydropower tuning and write its best configuration."""
    args = _build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(message)s",
    )
    study_name = (
        args.study_name or f"givp_hydropower_{args.scenario}_s{args.sampler_seed}"
    )
    payload = run_tuning(
        args.benchmark_root,
        scenario=args.scenario,
        n_trials=args.n_trials,
        n_eval_seeds=args.n_eval_seeds,
        sampler_seed=args.sampler_seed,
        max_iter=args.max_iter,
        time_limit=args.time_limit,
        study_name=study_name,
        storage=args.storage,
        verbose=args.verbose,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    metadata = cast(Mapping[str, object], payload["metadata"])
    best_params = cast(Mapping[str, object], payload["best_params"])
    _log.info("Best configuration written to %s", args.output)
    _log.info("Best objective value: %.6f", cast(float, metadata["best_value"]))
    _log.info("Best params:")
    for key, value in best_params.items():
        _log.info("  %s = %s", key, value)
    return 0
