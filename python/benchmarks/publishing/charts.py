# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
"""SVG benchmark chart generation."""

from __future__ import annotations

import math
from html import escape
from pathlib import Path

from benchmarks.publishing.models import ArtifactReport, SummaryRow
from benchmarks.publishing.tables import _fmt_number, _group_by_function

CHART_COLORS = ("#0f4c5c", "#e36414", "#6a994e", "#9a031e", "#5f0f40")


def _metric_value(row: SummaryRow, metric: str) -> float | None:
    """Return a numeric metric from a normalized row by symbolic name."""

    if metric == "mean_fun":
        return row.mean
    if metric == "time_mean_s":
        return row.time_mean_s
    msg = f"unsupported metric: {metric}"
    raise ValueError(msg)


def _scaled_width(
    value: float,
    min_positive: float,
    max_value: float,
    width: int,
) -> float:
    """Map a positive metric value to a log-scaled SVG bar width."""

    if math.isclose(max_value, min_positive):
        return width * 0.75
    numerator = math.log10(value) - math.log10(min_positive)
    denominator = math.log10(max_value) - math.log10(min_positive)
    return 8.0 + (numerator / denominator) * (width - 8.0)


def _append_chart_legend(
    lines: list[str], algorithms: list[str], canvas_width: int
) -> int:
    """Append the chart legend and return the final legend y coordinate."""

    legend_x = 24
    legend_y = 72
    legend_row_height = 20
    max_legend_x = canvas_width - 24
    for index, algorithm in enumerate(algorithms):
        color = CHART_COLORS[index % len(CHART_COLORS)]
        item_width = max(110, len(algorithm) * 8 + 30)
        if legend_x + item_width > max_legend_x:
            legend_x = 24
            legend_y += legend_row_height
        x = legend_x
        lines.append(
            f'<rect x="{x}" y="{legend_y - 12}" width="14" height="14" fill="{color}" rx="3" />'
        )
        lines.append(
            f'<text x="{x + 20}" y="{legend_y}" font-size="12" '
            f'font-family="Arial, sans-serif" fill="#374151">'
            f"{escape(algorithm)}</text>"
        )
        legend_x += item_width
    return legend_y


def _append_function_rows(
    lines: list[str],
    report: ArtifactReport,
    grouped: dict[str, dict[str, SummaryRow]],
    metric: str,
    left_pad: int,
    chart_width: int,
    row_gap: int,
    group_gap: int,
    min_positive: float,
    max_value: float,
    start_y: int,
) -> int:
    """Append per-function metric bars and return the resulting chart y offset."""

    current_y = start_y
    for function in report.functions:
        lines.append(
            f'<text x="24" y="{current_y + 5}" font-size="13" '
            f'font-family="Arial, sans-serif" fill="#111827">'
            f"{escape(function)}</text>"
        )
        for index, algorithm in enumerate(report.algorithms):
            row = grouped.get(function, {}).get(algorithm)
            value = _metric_value(row, metric) if row is not None else None
            if value is None or value <= 0:
                current_y += row_gap
                continue
            color = CHART_COLORS[index % len(CHART_COLORS)]
            bar_width = _scaled_width(value, min_positive, max_value, chart_width)
            bar_y = current_y - 7
            lines.extend(
                [
                    (
                        f'<rect x="{left_pad}" y="{bar_y}" width="{chart_width}" '
                        'height="12" fill="#e5e7eb" rx="6" />'
                    ),
                    (
                        f'<rect x="{left_pad}" y="{bar_y}" width="{bar_width:.2f}" '
                        f'height="12" fill="{color}" rx="6" />'
                    ),
                    (
                        f'<text x="{left_pad + chart_width + 16}" y="{current_y + 4}" '
                        'font-size="11" font-family="Arial, sans-serif" '
                        f'fill="#374151">{escape(algorithm)}: {_fmt_number(value)}</text>'
                    ),
                ]
            )
            current_y += row_gap
        current_y += group_gap
    return current_y


def write_metric_chart(report: ArtifactReport, metric: str, output_path: Path) -> None:
    """Render one grouped SVG bar chart for a normalized benchmark metric."""

    grouped = _group_by_function(report)
    values = [
        value
        for row in report.summary_rows
        if (value := _metric_value(row, metric)) is not None and value > 0
    ]
    if not values:
        return

    chart_width = 470
    left_pad = 170
    top_pad = 24
    row_gap = 24
    group_gap = 18
    title = "Mean objective value" if metric == "mean_fun" else "Mean runtime (s)"
    subtitle = "log10 scale, lower is better"
    label_samples = [
        f"{row.algorithm}: {_fmt_number(row.mean)}" for row in report.summary_rows
    ]
    longest_label_chars = max((len(sample) for sample in label_samples), default=16)
    right_col_width = max(210, longest_label_chars * 7)
    canvas_width = left_pad + chart_width + right_col_width + 56
    min_positive = min(values)
    max_value = max(values)

    lines = [
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_width}" '
            f'height="520" viewBox="0 0 {canvas_width} 520" role="img" '
            'aria-labelledby="title desc">'
        ),
        f"<title>{escape(report.label)} {escape(title)}</title>",
        (
            f"<desc>{escape(title)} for the generated {report.label} benchmark "
            "artifact page.</desc>"
        ),
        f'<rect x="0" y="0" width="{canvas_width}" height="100%" fill="#fffdf8" />',
        (
            f'<text x="24" y="32" font-size="24" '
            f'font-family="Arial, sans-serif" fill="#1f2937">'
            f"{escape(report.label)} {escape(title)}</text>"
        ),
        (
            f'<text x="24" y="54" font-size="13" '
            f'font-family="Arial, sans-serif" fill="#6b7280">'
            f"{escape(subtitle)}</text>"
        ),
    ]

    legend_y = _append_chart_legend(lines, report.algorithms, canvas_width)
    current_y = _append_function_rows(
        lines=lines,
        report=report,
        grouped=grouped,
        metric=metric,
        left_pad=left_pad,
        chart_width=chart_width,
        row_gap=row_gap,
        group_gap=group_gap,
        min_positive=min_positive,
        max_value=max_value,
        start_y=max(top_pad + 92, legend_y + 28),
    )

    height = current_y + 40
    lines[0] = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_width}" '
        f'height="{height}" viewBox="0 0 {canvas_width} {height}" role="img" '
        'aria-labelledby="title desc">'
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join([*lines, "</svg>"]), encoding="utf-8")


def has_metric(report: ArtifactReport, metric: str) -> bool:
    """Return whether the artifact exposes a positive value for the given metric."""

    return any(
        (value := _metric_value(row, metric)) is not None and value > 0
        for row in report.summary_rows
    )
