# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
"""Command-line interface for Optuna tuning."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import givp
from benchmarks.common.problems import PROBLEM_REGISTRY
from benchmarks.tuning.runner import run_tuning

_log = logging.getLogger(__name__)
_GIVP_VERSION = getattr(givp, "__version__", "unknown")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="tune_hyperparams",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
        "After tuning, use the output JSON with benchmarks.comparison:\n"
        "  python -m benchmarks.comparison \\\n"
            "      --algorithms GIVP-full GIVP-tuned GRASP-only \\\n"
            "      --tune-config best_config.json"
        ),
    )
    p.add_argument(
        "--n-trials",
        type=int,
        default=50,
        metavar="N",
        help=(
            "Number of Optuna trials (default: 50).  "
            "50 trials with default settings takes ~2-5 min."
        ),
    )
    p.add_argument(
        "--dims",
        type=int,
        default=5,
        metavar="N",
        help=(
            "Problem dimensionality for tuning (default: 5).  "
            "Lower = faster tuning; use 10 for publication-quality tuning."
        ),
    )
    p.add_argument(
        "--n-eval-seeds",
        type=int,
        default=3,
        metavar="N",
        help=(
            "Number of seeds per (trial, function) evaluation (default: 3).  "
            "Higher = more stable estimate, but slower."
        ),
    )
    p.add_argument(
        "--max-iter",
        type=int,
        default=100,
        metavar="N",
        help=(
            "Max GIVP iterations per evaluation within each trial (default: 100).  "
            "Keep low for fast tuning; increase for final validation."
        ),
    )
    p.add_argument(
        "--time-limit",
        type=float,
        default=10.0,
        metavar="SEC",
        help="Per-run wall-clock cap in seconds inside each trial (default: 10.0).",
    )
    p.add_argument(
        "--functions",
        nargs="+",
        default=["Sphere", "Rastrigin"],
        choices=list(PROBLEM_REGISTRY),
        metavar="FUNC",
        help=(
            f"Benchmark functions to tune on.  Choices: {list(PROBLEM_REGISTRY)}.  "
            "Default: Sphere Rastrigin (fast, representative)."
        ),
    )
    p.add_argument(
        "--sampler-seed",
        type=int,
        default=42,
        metavar="N",
        help="Seed for the Optuna TPE sampler (default: 42, fully reproducible).",
    )
    p.add_argument(
        "--study-name",
        type=str,
        default=None,
        metavar="NAME",
        help=(
            "Optuna study name (default: auto-generated from dims/functions/seed).  "
            "Used as identifier when --storage is set."
        ),
    )
    p.add_argument(
        "--storage",
        type=str,
        default=None,
        metavar="URL",
        help=(
            "Optuna storage URL for persistent studies (e.g. sqlite:///tune.db).  "
            "If omitted, uses in-memory storage (not persistent across crashes)."
        ),
    )
    p.add_argument(
        "--output",
        type=Path,
        default=Path("best_config.json"),
        metavar="PATH",
        help="Output JSON path for the best config (default: best_config.json).",
    )
    p.add_argument(
        "--verbose",
        action="store_true",
        help="Show Optuna INFO logs and progress bar.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: parse args, run Optuna study, save best config JSON."""
    args = _build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(message)s",
    )

    fn_tag = "_".join(args.functions[:3])
    study_name = args.study_name or (
        f"givp_tune_d{args.dims}_{fn_tag}_s{args.sampler_seed}"
    )

    _log.info("=" * 60)
    _log.info("GIVP -- Hyperparameter Tuning (Optuna TPE)")
    _log.info("=" * 60)
    _log.info("  givp version  : %s", _GIVP_VERSION)
    _log.info("  n_trials      : %s", args.n_trials)
    _log.info("  dims          : %s", args.dims)
    _log.info("  functions     : %s", args.functions)
    _log.info("  n_eval_seeds  : %s", args.n_eval_seeds)
    _log.info("  max_iter/run  : %s", args.max_iter)
    _log.info("  time_limit    : %ss per run", args.time_limit)
    _log.info("  sampler_seed  : %s", args.sampler_seed)
    _log.info("  study_name    : %s", study_name)
    _log.info("  storage       : %s", args.storage or "in-memory")
    _log.info("  output        : %s", args.output)
    est_runs = args.n_trials * len(args.functions) * args.n_eval_seeds
    est_min = est_runs * args.time_limit / 60
    _log.info(
        "  ~eval calls   : %d  (~%d min if all hit time_limit)", est_runs, int(est_min)
    )
    _log.info("")

    payload = run_tuning(
        functions=args.functions,
        dims=args.dims,
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
    _log.info("\nBest config saved -> %s", args.output.resolve())

    _log.info("\nBest hyperparameters:")
    for k, v in payload["best_trial_params"].items():
        _log.info("  %-30s = %s", k, v)

    _log.info(
        "\nRun the comparison with:\n"
        "  python -m benchmarks.comparison \\\n"
        "      --algorithms GIVP-full GIVP-tuned GRASP-only \\\n"
        "      --tune-config %s",
        args.output,
    )

    return 0
