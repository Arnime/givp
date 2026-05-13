# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
"""Generate reusable benchmark report pages for the documentation site.

This script normalizes the literature-comparison JSON artifacts committed under
``Notebooks/`` and publishes Markdown + SVG assets under ``docs/examples/``.

Usage
-----
    # Regenerate the committed benchmark report pages from the default artifacts
    python benchmarks/publish_docs_artifacts.py

    # Override the input artifacts (useful for testing)
    python benchmarks/publish_docs_artifacts.py \
        --artifact Python=tmp/python_results.json \
        --artifact Rust=tmp/rust_results.json
"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "docs" / "examples" / "benchmark-reports"
DEFAULT_REPO_URL_BASE = "https://github.com/Arnime/grasp_ils_vnd_pr/blob/main"
REGEN_COMMAND = "python benchmarks/publish_docs_artifacts.py"
DEFAULT_ARTIFACTS: tuple[tuple[str, str], ...] = (
    ("Python", "Notebooks/Python/benchmark_literature_comparison_results.json"),
    ("Julia", "Notebooks/Julia/results_notebook_julia.json"),
    ("Rust", "Notebooks/Rust/benchmark_literature_comparison_rust_results.json"),
    ("C++", "Notebooks/Cpp/benchmark_literature_comparison_cpp_results.json"),
    ("R", "Notebooks/R/benchmark_literature_comparison_r_results.json"),
)
CHART_COLORS = (
    "#0f4c5c",
    "#e36414",
    "#6a994e",
    "#9a031e",
    "#5f0f40",
)


@dataclass(frozen=True)
class SummaryRow:
    """Normalized summary statistics for one function/algorithm pair."""

    function: str
    algorithm: str
    n_runs: int | None
    mean: float
    std: float | None
    best: float | None
    median: float | None
    worst: float | None
    nfev_mean: float | None
    time_mean_s: float | None


@dataclass(frozen=True)
class ArtifactReport:
    """Normalized documentation payload for one committed benchmark artifact."""

    label: str
    slug: str
    source_path: Path
    source_repo_path: str
    metadata: dict[str, Any]
    summary_rows: list[SummaryRow]
    algorithms: list[str]
    functions: list[str]
    dims: int | None
    n_runs: int | None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for benchmark artifact publication."""

    parser = argparse.ArgumentParser(
        prog="publish_docs_artifacts",
        description="Publish benchmark artifact pages under docs/examples/.",
    )
    parser.add_argument(
        "--artifact",
        action="append",
        default=[],
        metavar="LABEL=PATH",
        help="Override one or more input artifacts. Can be passed multiple times.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory that will receive the generated Markdown and SVG files.",
    )
    parser.add_argument(
        "--repo-url-base",
        default=DEFAULT_REPO_URL_BASE,
        help="Base GitHub blob URL used for source links inside generated pages.",
    )
    return parser.parse_args(argv)


def parse_artifact_specs(values: list[str]) -> list[tuple[str, Path]]:
    """Resolve CLI artifact overrides or fall back to the committed defaults."""

    if not values:
        return [(label, REPO_ROOT / rel_path) for label, rel_path in DEFAULT_ARTIFACTS]

    specs: list[tuple[str, Path]] = []
    for value in values:
        if "=" not in value:
            msg = f"invalid --artifact value: {value!r}; expected LABEL=PATH"
            raise ValueError(msg)
        label, raw_path = value.split("=", 1)
        path = Path(raw_path).expanduser()
        if not path.is_absolute():
            path = (Path.cwd() / path).resolve()
        specs.append((label.strip(), path))
    return specs


def slugify(label: str) -> str:
    """Convert a report label into a stable documentation slug."""

    chars: list[str] = []
    for char in label.lower():
        if char.isalnum():
            chars.append(char)
        elif char == "+":
            chars.append("p")
        else:
            chars.append("-")
    slug = "".join(chars).strip("-")
    if slug == "c-pp":
        return "cpp"
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug or "artifact"


def _as_float(value: Any) -> float | None:
    """Convert a loosely typed JSON field to float when possible."""

    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> int | None:
    """Convert a loosely typed JSON field to int when possible."""

    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _pick(row: dict[str, Any], *keys: str) -> Any:
    """Return the first present key from a heterogeneous JSON row."""

    for key in keys:
        if key in row:
            return row[key]
    return None


def normalize_summary_rows(raw_summary: list[dict[str, Any]]) -> list[SummaryRow]:
    """Normalize per-language summary rows into a shared Python structure."""

    rows: list[SummaryRow] = []
    for row in raw_summary:
        function = _pick(row, "function", "function_name")
        algorithm = _pick(row, "algorithm")
        if not function or not algorithm:
            continue
        rows.append(
            SummaryRow(
                function=str(function),
                algorithm=str(algorithm),
                n_runs=_as_int(_pick(row, "n_runs")),
                mean=float(_pick(row, "mean", "mean_fun")),
                std=_as_float(_pick(row, "std", "sd_fun")),
                best=_as_float(_pick(row, "best", "best_fun")),
                median=_as_float(_pick(row, "median", "median_fun")),
                worst=_as_float(_pick(row, "worst", "worst_fun")),
                nfev_mean=_as_float(_pick(row, "nfev_mean", "nfev", "mean_nfev")),
                time_mean_s=_as_float(_pick(row, "time_s", "mean_time_s")),
            )
        )
    rows.sort(key=lambda item: (item.function, item.algorithm))
    return rows


def load_artifact(label: str, source_path: Path) -> ArtifactReport:
    """Load and normalize one committed literature-comparison artifact."""

    raw = json.loads(source_path.read_text(encoding="utf-8"))
    metadata = dict(raw.get("metadata", {}))
    summary_rows = normalize_summary_rows(raw.get("summary", []))
    if not summary_rows:
        msg = f"artifact {source_path} does not contain a usable summary"
        raise ValueError(msg)

    functions = list(dict.fromkeys(row.function for row in summary_rows))
    if "functions" in metadata:
        functions = [str(name) for name in metadata["functions"]]
    elif "benchmarks" in metadata:
        functions = [str(name) for name in metadata["benchmarks"]]

    algorithms = list(dict.fromkeys(row.algorithm for row in summary_rows))
    if "algorithms" in metadata:
        algorithms = [str(name) for name in metadata["algorithms"]]

    dims = _as_int(metadata.get("dims"))
    if dims is None:
        dims = _as_int(metadata.get("n_dims"))
    n_runs = _as_int(metadata.get("n_runs"))
    if n_runs is None:
        for row in summary_rows:
            if row.n_runs is not None:
                n_runs = row.n_runs
                break

    try:
        repo_path = source_path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        repo_path = source_path.resolve().as_posix()

    return ArtifactReport(
        label=label,
        slug=slugify(label),
        source_path=source_path.resolve(),
        source_repo_path=repo_path,
        metadata=metadata,
        summary_rows=summary_rows,
        algorithms=algorithms,
        functions=functions,
        dims=dims,
        n_runs=n_runs,
    )


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

    legend_x = 24
    legend_y = 72
    legend_row_height = 20
    max_legend_x = canvas_width - 24
    for index, algorithm in enumerate(report.algorithms):
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

    current_y = max(top_pad + 92, legend_y + 28)
    for function in report.functions:
        lines.append(
            f'<text x="24" y="{current_y + 5}" font-size="13" '
            f'font-family="Arial, sans-serif" fill="#111827">'
            f"{escape(function)}</text>"
        )
        for index, algorithm in enumerate(report.algorithms):
            row = grouped.get(function, {}).get(algorithm)
            if row is None:
                current_y += row_gap
                continue
            value = _metric_value(row, metric)
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


def build_page(report: ArtifactReport, repo_url_base: str) -> str:
    """Build one generated Markdown page for a normalized artifact."""

    source_url = f"{repo_url_base.rstrip('/')}/{report.source_repo_path}"
    dims = report.dims if report.dims is not None else "?"
    n_runs = report.n_runs if report.n_runs is not None else "?"
    functions = ", ".join(report.functions)
    algorithms = ", ".join(report.algorithms)
    lines = [
        f"<!-- Generated by {REGEN_COMMAND}; do not edit manually. -->",
        f"# {report.label} benchmark artifact",
        "",
        f"Source JSON: [{report.source_repo_path}]({source_url})",
        "",
        "## Metadata",
        "",
        f"- Dimensions: {dims}",
        f"- Independent runs: {n_runs}",
        f"- Algorithms: {algorithms}",
        f"- Functions: {functions}",
        "",
        "## Regenerate",
        "",
        "```bash",
        REGEN_COMMAND,
        "```",
        "",
        "## Generated charts",
        "",
    ]
    if has_metric(report, "mean_fun"):
        lines.extend(
            [
                f"![{report.label} mean objective value chart](assets/{report.slug}_mean_fun.svg)",
                "",
            ]
        )
    if has_metric(report, "time_mean_s"):
        lines.extend(
            [
                f"![{report.label} mean runtime chart](assets/{report.slug}_time_mean_s.svg)",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "Runtime mean was not present in the source summary, so no runtime SVG",
                "was generated for this artifact.",
                "",
            ]
        )
    lines.extend([build_pairwise_table(report), "", build_detailed_table(report)])
    return "\n".join(lines) + "\n"


def build_index(reports: list[ArtifactReport], repo_url_base: str) -> str:
    """Build the generated benchmark report index page."""

    lines = [
        f"<!-- Generated by {REGEN_COMMAND}; do not edit manually. -->",
        "# Benchmark reports",
        "",
        "These pages are generated from the committed literature-comparison artifacts",
        "under `Notebooks/` and are intended to be the canonical docs-facing view of",
        "those benchmark results.",
        "",
        "## Regenerate",
        "",
        "```bash",
        REGEN_COMMAND,
        "```",
        "",
        "## Available artifacts",
        "",
        "| Language | Source JSON | Dims | Runs | Page |",
        "|---|---|---|---|---|",
    ]
    for report in reports:
        source_url = f"{repo_url_base.rstrip('/')}/{report.source_repo_path}"
        dims = report.dims if report.dims is not None else "?"
        runs = report.n_runs if report.n_runs is not None else "?"
        lines.append(
            "| "
            + " | ".join(
                [
                    report.label,
                    f"[{report.source_repo_path}]({source_url})",
                    str(dims),
                    str(runs),
                    f"[{report.label} report]({report.slug}.md)",
                ]
            )
            + " |"
        )
    lines.append("")
    return "\n".join(lines)


def write_report_page(
    report: ArtifactReport, output_dir: Path, repo_url_base: str
) -> None:
    """Write one generated page plus its SVG assets to the docs tree."""

    page_path = output_dir / f"{report.slug}.md"
    page_path.write_text(build_page(report, repo_url_base), encoding="utf-8")
    assets_dir = output_dir / "assets"
    write_metric_chart(report, "mean_fun", assets_dir / f"{report.slug}_mean_fun.svg")
    write_metric_chart(
        report,
        "time_mean_s",
        assets_dir / f"{report.slug}_time_mean_s.svg",
    )


def main(argv: list[str] | None = None) -> int:
    """Generate all benchmark report pages and return a process exit code."""

    args = parse_args(argv)
    try:
        specs = parse_artifact_specs(args.artifact)
        reports = [load_artifact(label, path) for label, path in specs]
    except (OSError, ValueError) as exc:
        print(f"[error] {exc}")
        return 1

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    output_dir.joinpath("index.md").write_text(
        build_index(reports, args.repo_url_base),
        encoding="utf-8",
    )
    for report in reports:
        write_report_page(report, output_dir, args.repo_url_base)

    print(f"Generated {len(reports)} benchmark report pages in {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
