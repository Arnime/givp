# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
"""Documentation benchmark tables."""

from __future__ import annotations

from collections import defaultdict

from benchmarks.publishing.models import ArtifactReport, SummaryRow


def _fmt_number(value: float | None) -> str:
    """Format numeric values consistently for generated Markdown tables."""

    if value is None:
        return "-"
    if value == 0:
        return "0"
    magnitude = abs(value)
    if magnitude >= 1000 or magnitude < 0.001:
        return f"{value:.4e}"
    if magnitude >= 100:
        return f"{value:.2f}"
    if magnitude >= 1:
        return f"{value:.4f}"
    return f"{value:.6f}".rstrip("0").rstrip(".")


def _fmt_mean_std(row: SummaryRow) -> str:
    """Render a mean/std pair in the generated docs table style."""

    if row.std is None:
        return _fmt_number(row.mean)
    return f"{_fmt_number(row.mean)} +- {_fmt_number(row.std)}"


def _fmt_ratio(numerator: float | None, denominator: float | None) -> str:
    """Render a runtime ratio when both operands are available."""

    if numerator is None or denominator is None or denominator == 0:
        return "-"
    return f"{numerator / denominator:.2f}x"


def _group_by_function(report: ArtifactReport) -> dict[str, dict[str, SummaryRow]]:
    """Index normalized rows by function and algorithm."""

    grouped: dict[str, dict[str, SummaryRow]] = defaultdict(dict)
    for row in report.summary_rows:
        grouped[row.function][row.algorithm] = row
    return dict(grouped)


def build_pairwise_table(report: ArtifactReport) -> str:
    """Build the high-level per-function Markdown summary table."""

    grouped = _group_by_function(report)
    baseline = "GIVP-full" if "GIVP-full" in report.algorithms else report.algorithms[0]
    comparator = (
        "GRASP-only"
        if "GRASP-only" in report.algorithms
        else next((algo for algo in report.algorithms if algo != baseline), baseline)
    )

    lines = [
        "## Function-level summary",
        "",
        (
            f"| Function | {baseline} mean +- std | {comparator} mean +- std "
            f"| Runtime ratio ({baseline}/{comparator}) |"
        ),
        "|---|---|---|---|",
    ]
    for function in report.functions:
        baseline_row = grouped.get(function, {}).get(baseline)
        comparator_row = grouped.get(function, {}).get(comparator)
        lines.append(
            "| "
            + " | ".join(
                [
                    function,
                    _fmt_mean_std(baseline_row) if baseline_row else "-",
                    _fmt_mean_std(comparator_row) if comparator_row else "-",
                    _fmt_ratio(
                        baseline_row.time_mean_s if baseline_row else None,
                        comparator_row.time_mean_s if comparator_row else None,
                    ),
                ]
            )
            + " |"
        )
    return "\n".join(lines)


def build_detailed_table(report: ArtifactReport) -> str:
    """Build the detailed Markdown table emitted on each artifact page."""

    lines = [
        "## Detailed summary rows",
        "",
        "| Function | Algorithm | Mean +- std | Median | Mean nfev | Mean time (s) |",
        "|---|---|---|---|---|---|",
    ]
    for row in report.summary_rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    row.function,
                    row.algorithm,
                    _fmt_mean_std(row),
                    _fmt_number(row.median),
                    _fmt_number(row.nfev_mean),
                    _fmt_number(row.time_mean_s),
                ]
            )
            + " |"
        )
    return "\n".join(lines)
