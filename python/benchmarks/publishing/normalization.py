# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
"""Cross-language artifact normalization."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from benchmarks.publishing.models import ArtifactReport, SummaryRow

DEFAULT_ARTIFACTS: tuple[tuple[str, str], ...] = (
    ("Python", "Notebooks/Python/benchmark_literature_comparison_results.json"),
    ("Julia", "Notebooks/Julia/results_notebook_julia.json"),
    ("Rust", "Notebooks/Rust/benchmark_literature_comparison_rust_results.json"),
    ("C++", "Notebooks/Cpp/benchmark_literature_comparison_cpp_results.json"),
    ("R", "Notebooks/R/benchmark_literature_comparison_r_results.json"),
)


def parse_artifact_specs(
    values: list[str], repo_root: Path
) -> list[tuple[str, Path]]:
    """Resolve CLI artifact overrides or fall back to the committed defaults."""

    if not values:
        return [(label, repo_root / rel_path) for label, rel_path in DEFAULT_ARTIFACTS]

    specs: list[tuple[str, Path]] = []
    for value in values:
        if "=" not in value:
            msg = f"invalid --artifact value: {value!r}; expected LABEL=PATH"
            raise ValueError(msg)
        label, raw_path = value.split("=", 1)
        path = Path(raw_path).expanduser()
        if not path.is_absolute():
            path = (repo_root / path).resolve()
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


def load_artifact(
    label: str, source_path: Path, repo_root: Path
) -> ArtifactReport:
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
        repo_path = source_path.resolve().relative_to(repo_root.resolve()).as_posix()
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
