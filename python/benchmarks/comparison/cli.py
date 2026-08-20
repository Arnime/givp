# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
"""Command-line interface for literature comparisons."""

from __future__ import annotations

import argparse
import json
import logging
import time
from pathlib import Path

import givp
from benchmarks.common.problems import ALGO_DESCRIPTIONS, PROBLEM_REGISTRY
from benchmarks.comparison.execution import run_experiment
from givp import GIVPConfig

_GIVP_VERSION = getattr(givp, "__version__", "unknown")

_log = logging.getLogger(__name__)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m benchmarks.comparison",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Output JSON is consumed by benchmarks.reporting to produce\n"
            "Markdown/LaTeX tables, boxplots, and Wilcoxon test results."
        ),
    )
    p.add_argument(
        "--dims",
        type=int,
        default=10,
        metavar="N",
        help="Problem dimensionality, i.e. number of decision variables (default: 10).",
    )
    p.add_argument(
        "--n-runs",
        type=int,
        default=30,
        metavar="N",
        help=(
            "Independent runs per (algorithm, function) pair (default: 30). "
            ">=30 is recommended for publication-quality statistics."
        ),
    )
    p.add_argument(
        "--seed-start",
        type=int,
        default=0,
        metavar="N",
        help="First seed; runs use seeds [N, N + n_runs) (default: 0).",
    )
    p.add_argument(
        "--max-iter",
        type=int,
        default=200,
        metavar="N",
        help="Max iterations per run (default: 200).",
    )
    p.add_argument(
        "--time-limit",
        type=float,
        default=30.0,
        metavar="SEC",
        help="Per-run wall-clock time limit in seconds (default: 30.0).",
    )
    p.add_argument(
        "--algorithms",
        nargs="+",
        default=["GIVP-full", "DE", "PSO", "GA", "CMA-ES", "SA"],
        choices=list(ALGO_DESCRIPTIONS),
        metavar="ALGO",
        help=(
            "Algorithms to include.  Choices: "
            f"{list(ALGO_DESCRIPTIONS)}.  "
            "DE and SA require scipy. PSO/GA/CMA-ES require pymoo.  "
            "Default: GIVP-full DE PSO GA CMA-ES SA."
        ),
    )
    p.add_argument(
        "--functions",
        nargs="+",
        default=list(PROBLEM_REGISTRY),
        choices=list(PROBLEM_REGISTRY),
        metavar="FUNC",
        help=(
            f"Benchmark functions.  Choices: {list(PROBLEM_REGISTRY)}.  "
            "Default: all six functions."
        ),
    )
    p.add_argument(
        "--output",
        type=Path,
        default=Path("experiment_results.json"),
        metavar="PATH",
        help="Output JSON file path (default: experiment_results.json).",
    )
    p.add_argument(
        "--tune-config",
        type=Path,
        default=None,
        metavar="PATH",
        help=(
            "Path to JSON produced by benchmarks.tuning.  "
            "Required when GIVP-tuned is in --algorithms."
        ),
    )
    p.add_argument(
        "--traces",
        action="store_true",
        help=(
            "Capture per-iteration best-value history for GIVP algorithms. "
            "Enables convergence plots in benchmarks.reporting.  "
            "Increases output file size."
        ),
    )
    p.add_argument(
        "--resume",
        action="store_true",
        help=(
            "Resume from an existing --output file: skip functions that already "
            "have complete results in the checkpoint and continue from where "
            "the experiment left off."
        ),
    )
    p.add_argument(
        "--verbose",
        action="store_true",
        help="Print progress after each run.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: parse arguments, run experiment, save JSON, print summary."""
    args = _build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(message)s",
    )

    givp_tuned_config: GIVPConfig | None = None
    if "GIVP-tuned" in args.algorithms:
        if args.tune_config is None:
            _log.error(
                "[error] --algorithms GIVP-tuned requires --tune-config PATH\n"
                "        Run tune_hyperparams.py first to generate a config file."
            )
            return 1
        tune_data = json.loads(args.tune_config.read_text(encoding="utf-8"))
        params = tune_data.get("best_params", tune_data)
        givp_tuned_config = GIVPConfig(**params)

    n_total = len(args.algorithms) * len(args.functions) * args.n_runs
    est_min = n_total * 0.5 / 60  # rough estimate assuming ~0.5s per run

    _log.info("=" * 60)
    _log.info("GIVP -- Literature Comparison Benchmark")
    _log.info("=" * 60)
    _log.info("  givp version  : %s", _GIVP_VERSION)
    _log.info("  dims          : %s", args.dims)
    _log.info(
        "  n_runs        : %d  (seeds %d-%d)",
        args.n_runs,
        args.seed_start,
        args.seed_start + args.n_runs - 1,
    )
    _log.info("  max_iter      : %s", args.max_iter)
    _log.info("  time_limit    : %ss per run", args.time_limit)
    _log.info("  algorithms    : %s", args.algorithms)
    _log.info("  functions     : %s", args.functions)
    _log.info("  capture traces: %s", args.traces)
    _log.info("  total runs    : %d  (~%d min estimated)", n_total, int(est_min))
    _log.info("  output        : %s", args.output)
    _log.info("")

    t_wall = time.perf_counter()
    payload = run_experiment(
        algorithms=args.algorithms,
        functions=args.functions,
        dims=args.dims,
        n_runs=args.n_runs,
        seed_start=args.seed_start,
        max_iter=args.max_iter,
        time_limit=args.time_limit,
        capture_traces=args.traces,
        givp_tuned_config=givp_tuned_config,
        checkpoint_path=args.output,
        resume=args.resume,
    )
    elapsed = time.perf_counter() - t_wall

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    _log.info("\nFinished in %.1fs -> %s", elapsed, args.output.resolve())
    _log.info("")

    col_w = 14
    header = (
        f"{'Function':<{col_w}} {'Algorithm':<{col_w}} "
        f"{'Mean':>12} {'Std':>12} {'Best':>12} {'Median':>12}"
    )
    _log.info(header)
    _log.info("-" * len(header))
    for row in payload["summary"]:
        _log.info(
            "%s %s %12.4e %12.4e %12.4e %12.4e",
            f"{row['function']:<{col_w}}",
            f"{row['algorithm']:<{col_w}}",
            row["mean"],
            row["std"],
            row["best"],
            row["median"],
        )

    return 0
