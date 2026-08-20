# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
"""Command-line interface for statistical reports."""

from __future__ import annotations

import argparse
import logging
import textwrap
from pathlib import Path

from benchmarks.reporting.console import print_console_summary
from benchmarks.reporting.figures import _MPL_OK, plot_boxplot, plot_convergence
from benchmarks.reporting.latex import to_latex
from benchmarks.reporting.loading import load_results
from benchmarks.reporting.markdown import to_markdown
from benchmarks.reporting.statistics import (
    _SCIPY_OK,
    friedman_table,
    holm_bonferroni_correction,
    wilcoxon_table,
)

_log = logging.getLogger(__name__)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m benchmarks.reporting",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--input",
        type=Path,
        required=True,
        metavar="PATH",
        help="JSON file produced by benchmarks.comparison.",
    )
    p.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        metavar="DIR",
        help=(
            "Directory for output files (tables + plots).  "
            "Defaults to the same directory as --input."
        ),
    )
    p.add_argument(
        "--format",
        choices=["markdown", "latex", "both"],
        default="both",
        help="Table format(s) to generate (default: both).",
    )
    p.add_argument(
        "--no-plots",
        action="store_true",
        help="Skip boxplot and convergence PNG generation.",
    )
    p.add_argument(
        "--reference",
        type=str,
        default=None,
        metavar="ALGO",
        help=(
            "Reference algorithm for Wilcoxon pairwise tests.  "
            "Defaults to the first algorithm in the JSON."
        ),
    )
    p.add_argument(
        "--alpha",
        type=float,
        default=0.05,
        metavar="FLOAT",
        help="Significance level for Wilcoxon tests (default: 0.05).",
    )
    p.add_argument(
        "--no-holm",
        action="store_true",
        help="Disable Holm-Bonferroni correction in reported p-values.",
    )
    p.add_argument(
        "--no-friedman",
        action="store_true",
        help="Disable Friedman omnibus test section in reports.",
    )
    p.add_argument(
        "--trace-seed",
        type=int,
        default=0,
        metavar="N",
        help="Seed to use for convergence trace plot (default: 0).",
    )
    p.add_argument(
        "--verbose",
        action="store_true",
        help="Show DEBUG-level messages (per-record Wilcoxon details, file paths).",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: load results JSON, run statistical tests, write reports."""
    args = _build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(message)s",
    )

    if not args.input.exists():
        _log.error("[error] Input file not found: %s", args.input)
        return 1

    meta, records, summary = load_results(args.input)
    out_dir = args.output_dir or args.input.parent
    stem = args.input.stem

    _log.debug("Loaded %d records, %d summary rows", len(records), len(summary))

    algorithms = meta.get("algorithms", sorted({r.algorithm for r in records}))
    reference = args.reference or (algorithms[0] if algorithms else "GIVP-full")

    if reference not in {r.algorithm for r in records}:
        _log.error(
            "[error] Reference algorithm %r not found in records.\n"
            "        Available: %s",
            reference,
            sorted({r.algorithm for r in records}),
        )
        return 1

    _log.info("Report for: %s", args.input)
    _log.info("  algorithms  : %s", algorithms)
    _log.info("  functions   : %s", meta.get("functions", "?"))
    _log.info("  dims        : %s", meta.get("dims", "?"))
    _log.info("  n_runs      : %s", meta.get("n_runs", "?"))
    _log.info("  reference   : %s", reference)
    _log.info("  alpha       : %s", args.alpha)
    _log.info("")

    # Wilcoxon tests
    wrows = wilcoxon_table(records, reference=reference, alpha=args.alpha)
    holm_p_idx, holm_sig_idx = (
        ({}, {})
        if args.no_holm
        else holm_bonferroni_correction(wrows, alpha=args.alpha)
    )
    frows = [] if args.no_friedman else friedman_table(records, alpha=args.alpha)
    _log.debug(
        "Wilcoxon: %d significant pairs out of %d",
        sum(w.significant for w in wrows),
        len(wrows),
    )

    # Console summary
    print_console_summary(summary, wrows, holm_p_idx, holm_sig_idx, frows)

    if not _SCIPY_OK:
        _log.warning(
            textwrap.dedent("""\
            [note] scipy not installed - statistical significance tests skipped.
                   Install with:  pip install scipy
            """)
        )

    # Markdown
    if args.format in ("markdown", "both"):
        md_path = out_dir / f"{stem}_report.md"
        md_path.parent.mkdir(parents=True, exist_ok=True)
        meta["reference_algorithm"] = reference
        md_path.write_text(
            to_markdown(summary, wrows, meta, holm_p_idx, holm_sig_idx, frows),
            encoding="utf-8",
        )
        _log.info("Markdown table -> %s", md_path)

    # LaTeX
    if args.format in ("latex", "both"):
        tex_path = out_dir / f"{stem}_report.tex"
        tex_path.parent.mkdir(parents=True, exist_ok=True)
        tex_path.write_text(
            to_latex(summary, wrows, meta, holm_p_idx, holm_sig_idx, frows),
            encoding="utf-8",
        )
        _log.info("LaTeX table    -> %s", tex_path)

    # Plots
    if not args.no_plots:
        if not _MPL_OK:
            _log.warning(
                "[note] matplotlib not installed - plots skipped.\n"
                "       Install with:  pip install matplotlib"
            )
        else:
            plot_boxplot(records, meta, out_dir / f"{stem}_boxplot.png")
            plot_convergence(
                records,
                meta,
                out_dir / f"{stem}_convergence.png",
                trace_seed=args.trace_seed,
            )

    _log.info("\nDone.")
    return 0
