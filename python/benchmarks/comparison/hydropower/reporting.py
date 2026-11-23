# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
"""Render dissertation-ready tables and figures from hydropower campaign rows."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import cast

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import sem, t, wilcoxon

# Preferred display order; anything else found in the runs is appended.
_ALGORITHMS = ("DE", "PSO", "UPSO", "GIVP")
_REFERENCE = "GIVP"
_SCENARIOS = (
    "dry_stable",
    "dry_variable",
    "typical",
    "upstream_peak",
    "downstream_dominant",
    "wet_rising",
    "flood",
)
# Optional hydraulic columns rendered as extra box plots when present.
_HYDRAULIC_PLOTS = (
    ("power_deficit_mwh", "Déficit de potência (MWh)", "deficit_boxplots.png"),
    ("spill_hm3", "Vertimento (hm³)", "spill_boxplots.png"),
    ("final_level_a_m", "Nível final da usina A (m)", "final_level_a_boxplots.png"),
    ("final_level_b_m", "Nível final da usina B (m)", "final_level_b_boxplots.png"),
)


def main() -> None:
    """Summarize one completed or partial campaign without changing its run rows."""
    args = _build_parser().parse_args()
    render_reports(
        args.runs.resolve(strict=True), args.output_dir.resolve(strict=False)
    )


def render_reports(runs_path: Path, output_dir: Path) -> list[Path]:
    """Write CSV, LaTex and PNG artifacts from valid completed campaign rows."""
    records = pd.read_csv(runs_path)
    _validate_records(records)
    output_dir.mkdir(parents=True, exist_ok=True)
    summary = _summary(records)
    paths = [
        _write_csv(summary, output_dir / "summary_by_scenario.csv"),
        _write_csv(_overall_summary(records), output_dir / "summary_overall.csv"),
        _write_csv(_rank_summary(records), output_dir / "rank_by_scenario.csv"),
        _write_csv(_paired_statistics(records), output_dir / "paired_statistics.csv"),
        _write_latex(summary, output_dir / "summary_by_scenario.tex"),
        _metric_boxplots(
            records,
            "objective",
            "Objetivo",
            "Distribuição do objetivo por cenário",
            output_dir / "objective_boxplots.png",
        ),
        _metric_boxplots(
            records,
            "energy_mwh",
            "Energia entregue (MWh)",
            "Distribuição da energia entregue por cenário",
            output_dir / "energy_boxplots.png",
        ),
        _median_heatmap(summary, output_dir / "median_objective_heatmap.png"),
    ]
    for column, label, filename in _HYDRAULIC_PLOTS:
        if column in records:
            paths.append(
                _metric_boxplots(
                    records,
                    column,
                    label,
                    f"{label} por cenário",
                    output_dir / filename,
                )
            )
    return paths


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser


def _validate_records(records: pd.DataFrame) -> None:
    required = {"scenario", "algorithm", "replication", "objective", "energy_mwh"}
    missing = required - set(records.columns)
    if missing:
        raise ValueError(
            f"runs CSV lacks required columns: {', '.join(sorted(missing))}"
        )
    if records.empty:
        raise ValueError("runs CSV contains no completed optimizer runs")
    if (
        not np.isfinite(records["objective"]).all()
        or not np.isfinite(records["energy_mwh"]).all()
    ):
        raise ValueError("runs CSV contains a non-finite objective or energy value")


def _summary(records: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        records.groupby(["scenario", "algorithm"], observed=True)
        .agg(
            runs=("objective", "size"),
            objective_median=("objective", "median"),
            objective_mean=("objective", "mean"),
            objective_std=("objective", "std"),
            energy_mwh_median=("energy_mwh", "median"),
            energy_mwh_mean=("energy_mwh", "mean"),
            level_penalty_median=("level_penalty", "median"),
            power_deficit_mwh_median=("power_deficit_mwh", "median"),
            evaluations_median=("evaluations", "median"),
            **(
                {"spill_hm3_median": ("spill_hm3", "median")}
                if "spill_hm3" in records
                else {}
            ),
            elapsed_seconds_median=("elapsed_seconds", "median"),
        )
        .reset_index()
    )
    confidence = (
        records.groupby(["scenario", "algorithm"], observed=True)["objective"]
        .apply(_confidence_interval)
        .apply(pd.Series)
        .reset_index()
        .rename(columns={0: "objective_ci_low", 1: "objective_ci_high"})
    )
    grouped = grouped.merge(confidence, on=["scenario", "algorithm"])
    return _ordered(grouped)


def _confidence_interval(values: pd.Series) -> tuple[float, float]:
    """Return a deterministic 95% Student confidence interval."""
    array = values.to_numpy(dtype=float)
    mean = float(np.mean(array))
    if array.size < 2 or np.allclose(array, array[0]):
        return mean, mean
    margin = float(t.ppf(0.975, array.size - 1) * sem(array))
    return mean - margin, mean + margin


def _paired_statistics(records: pd.DataFrame) -> pd.DataFrame:
    """Compare GIVP to each competitor with paired Wilcoxon and Holm correction."""
    normalized = records.copy()
    scales = normalized.groupby("scenario", observed=True)["objective"].transform(
        lambda values: max(float(np.median(np.abs(values))), 1.0)
    )
    normalized["normalized_objective"] = normalized["objective"] / scales
    pivot = normalized.pivot_table(
        index=["scenario", "replication"],
        columns="algorithm",
        values="normalized_objective",
        aggfunc="first",
    )
    rows: list[dict[str, float | int | str]] = []
    scopes = {"overall": pivot}
    if "flood" in pivot.index.get_level_values(0):
        scopes["flood"] = pivot.loc[pivot.index.get_level_values(0) == "flood"]
    competitors = [
        algorithm for algorithm in _algorithms(records) if algorithm != _REFERENCE
    ]
    if _REFERENCE not in pivot.columns:
        competitors = []
    for scope, scoped_pivot in scopes.items():
        for competitor in competitors:
            paired = scoped_pivot.loc[:, [_REFERENCE, competitor]].dropna()
            if paired.empty:
                continue
            difference = paired[_REFERENCE] - paired[competitor]
            p_value = (
                1.0
                if np.allclose(difference, 0.0)
                else float(wilcoxon(difference, alternative="less").pvalue)
            )
            rows.append(
                {
                    "scope": scope,
                    "comparison": f"GIVP < {competitor}",
                    "pairs": len(paired),
                    "givp_win_rate": float((difference < 0).mean()),
                    "median_normalized_difference": float(difference.median()),
                    "p_value": p_value,
                }
            )
    if not rows:
        return pd.DataFrame(
            columns=[
                "scope",
                "comparison",
                "pairs",
                "givp_win_rate",
                "median_normalized_difference",
                "p_value",
                "holm_p_value",
                "significant_0_05",
            ]
        )
    order = sorted(range(len(rows)), key=lambda index: float(rows[index]["p_value"]))
    adjusted = [1.0] * len(rows)
    running = 0.0
    for rank, index in enumerate(order):
        candidate = min(1.0, (len(rows) - rank) * float(rows[index]["p_value"]))
        running = max(running, candidate)
        adjusted[index] = running
    for row, value in zip(rows, adjusted, strict=True):
        row["holm_p_value"] = value
        row["significant_0_05"] = value < 0.05
    return pd.DataFrame(rows)


def _overall_summary(records: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        records.groupby("algorithm", observed=True)
        .agg(
            runs=("objective", "size"),
            objective_median=("objective", "median"),
            objective_mean=("objective", "mean"),
            energy_mwh_median=("energy_mwh", "median"),
            elapsed_seconds_total=("elapsed_seconds", "sum"),
            evaluations_total=("evaluations", "sum"),
        )
        .reset_index()
    )
    return _ordered(grouped)


def _rank_summary(records: pd.DataFrame) -> pd.DataFrame:
    ranked = records.copy()
    ranked["rank"] = ranked.groupby(["scenario", "replication"], observed=True)[
        "objective"
    ].rank(method="average", ascending=True)
    grouped = (
        ranked.groupby(["scenario", "algorithm"], observed=True)["rank"]
        .agg(["mean", "median", "std", "count"])
        .reset_index()
        .rename(
            columns={
                "count": "runs",
                "mean": "mean_rank",
                "median": "median_rank",
                "std": "rank_std",
            }
        )
    )
    return _ordered(grouped)


def _algorithms(records: pd.DataFrame) -> tuple[str, ...]:
    return _display_order(records["algorithm"].astype(str), _ALGORITHMS)


def _scenarios(records: pd.DataFrame) -> tuple[str, ...]:
    return _display_order(records["scenario"].astype(str), _SCENARIOS)


def _display_order(values: pd.Series, preferred: tuple[str, ...]) -> tuple[str, ...]:
    present = list(dict.fromkeys(values))
    known = [item for item in preferred if item in present]
    return (*known, *sorted(item for item in present if item not in preferred))


def _ordered(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    sort_fields: list[str] = []
    if "scenario" in result:
        result["scenario"] = pd.Categorical(
            result["scenario"], _scenarios(result), ordered=True
        )
        sort_fields.append("scenario")
    if "algorithm" in result:
        result["algorithm"] = pd.Categorical(
            result["algorithm"], _algorithms(result), ordered=True
        )
        sort_fields.append("algorithm")
    return result.sort_values(sort_fields, ignore_index=True)


def _write_csv(frame: pd.DataFrame, path: Path) -> Path:
    frame.to_csv(path, index=False, float_format="%.6f")
    return path


def _write_latex(summary: pd.DataFrame, path: Path) -> Path:
    table = summary.loc[
        :,
        [
            "scenario",
            "algorithm",
            "runs",
            "objective_median",
            "objective_std",
            "energy_mwh_median",
        ],
    ].copy()
    table.columns = [
        "Cenário",
        "Algoritmo",
        "Execuções",
        "Objetivo (mediana)",
        "Objetivo (DP)",
        "Energia (MWh, mediana)",
    ]
    path.write_text(
        table.to_latex(index=False, float_format="%.6f", escape=True), encoding="utf-8"
    )
    return path


def _metric_boxplots(
    records: pd.DataFrame, column: str, ylabel: str, title: str, path: Path
) -> Path:
    scenarios = _scenarios(records)
    algorithms = _algorithms(records)
    columns = min(4, len(scenarios))
    rows = -(-len(scenarios) // columns)
    figure, axes = plt.subplots(
        rows, columns, figsize=(3.75 * columns, 3.5 * rows), squeeze=False
    )
    for axis, scenario in zip(axes.flat, scenarios, strict=False):
        subset = records.loc[records["scenario"] == scenario]
        values = [
            subset.loc[subset["algorithm"] == algorithm, column].to_numpy(dtype=float)
            for algorithm in algorithms
        ]
        _boxplot(axis, values, algorithms, ylabel, scenario)
    for axis in list(axes.flat)[len(scenarios) :]:
        axis.axis("off")
    figure.suptitle(f"{title} ({_replication_label(records)})")
    figure.tight_layout()
    figure.savefig(path, dpi=180)
    plt.close(figure)
    return path


def _replication_label(records: pd.DataFrame) -> str:
    counts = records.groupby(["scenario", "algorithm"], observed=True).size()
    low, high = int(counts.min()), int(counts.max())
    count = str(low) if low == high else f"{low} a {high}"
    return f"{count} repetição" if count == "1" else f"{count} repetições"


def _boxplot(
    axis: plt.Axes,
    values: list[np.ndarray],
    labels: tuple[str, ...],
    ylabel: str,
    title: str,
) -> None:
    visible = [value if len(value) else np.array([np.nan]) for value in values]
    axis.boxplot(visible, tick_labels=labels, showmeans=True)
    axis.set(title=title, ylabel=ylabel)
    axis.tick_params(axis="x", rotation=25)


def _median_heatmap(summary: pd.DataFrame, path: Path) -> Path:
    scenarios = _scenarios(summary)
    algorithms = _algorithms(summary)
    matrix = summary.pivot(
        index="scenario", columns="algorithm", values="objective_median"
    ).reindex(index=list(scenarios), columns=list(algorithms))
    figure, axis = plt.subplots(figsize=(8.5, 5.5))
    image = axis.imshow(matrix.to_numpy(dtype=float), cmap="viridis", aspect="auto")
    axis.set(
        title="Mediana do objetivo (menor é melhor)",
        xticks=np.arange(len(algorithms)),
        yticks=np.arange(len(scenarios)),
        xticklabels=algorithms,
        yticklabels=scenarios,
    )
    for row, scenario in enumerate(scenarios):
        for column, algorithm in enumerate(algorithms):
            value = cast(float, matrix.loc[scenario, algorithm])
            if np.isfinite(value):
                axis.text(
                    column, row, f"{value:.1f}", ha="center", va="center", color="white"
                )
    figure.colorbar(image, ax=axis, label="Objetivo")
    figure.tight_layout()
    figure.savefig(path, dpi=180)
    plt.close(figure)
    return path


if __name__ == "__main__":
    main()
