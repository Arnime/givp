"""Render deterministic figures from frozen synthetic benchmark results."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Final

import matplotlib.pyplot as plt
import pandas as pd
from givp.examples.synthetic_hydropower.model import PlantConfig

PERIOD_LABEL = "Período"
UPPER_RIGHT_LEGEND: Final = "upper right"


def render_figures(
    reference_results_dir: Path,
    config_path: Path,
    figures_dir: Path,
) -> list[Path]:
    """Render power, flow and level figures from a frozen time-series CSV."""
    time_series_path = reference_results_dir / "benchmark_time_series.csv"
    if not time_series_path.is_file():
        raise FileNotFoundError(f"missing reference time series: {time_series_path}")
    if not config_path.is_file():
        raise FileNotFoundError(f"missing benchmark configuration: {config_path}")

    records = pd.read_csv(time_series_path)
    plant_payload = json.loads(config_path.read_text(encoding="utf-8"))
    plants = {plant["name"]: PlantConfig(**plant) for plant in plant_payload["plants"]}
    figures_dir.mkdir(parents=True, exist_ok=True)
    figures: list[Path] = []
    for scenario_key, scenario_records in records.groupby("scenario", sort=False):
        if not isinstance(scenario_key, str):
            raise TypeError("scenario values in reference results must be strings")
        scenario_slug = _scenario_slug(scenario_key)
        figures.extend(
            (
                _render_power(
                    scenario_records, figures_dir, scenario_key, scenario_slug
                ),
                _render_flows(
                    scenario_records, plants, figures_dir, scenario_key, scenario_slug
                ),
                _render_levels(
                    scenario_records, plants, figures_dir, scenario_key, scenario_slug
                ),
            )
        )
    return figures


def _render_power(
    records: pd.DataFrame, figures_dir: Path, scenario_name: str, slug: str
) -> Path:
    """Render grouped power bars for one scenario."""
    plant_a = records.loc[records["plant"] == "A"].sort_values("period")
    plant_b = records.loc[records["plant"] == "B"].sort_values("period")
    periods = plant_a["period"].to_numpy()
    figure, axis = plt.subplots(figsize=(14, 4.5))
    axis.bar(periods - 0.21, plant_a["power_mw"], width=0.42, label="Usina A")
    axis.bar(periods + 0.21, plant_b["power_mw"], width=0.42, label="Usina B")
    axis.set(
        title=f"Potência — cenário: {scenario_name}", xlabel=PERIOD_LABEL, ylabel="MW"
    )
    axis.legend(loc=UPPER_RIGHT_LEGEND)
    figure.tight_layout()
    path = figures_dir / f"{slug}_power.png"
    figure.savefig(path, dpi=160)
    plt.close(figure)
    return path


def _render_flows(
    records: pd.DataFrame,
    plants: dict[str, PlantConfig],
    figures_dir: Path,
    scenario_name: str,
    slug: str,
) -> Path:
    """Render arrival, turbine and spill flows for both plants."""
    figure, axes = plt.subplots(2, 1, figsize=(14, 7), sharex=True)
    for axis, plant_name in zip(axes, ("A", "B"), strict=True):
        plant_records = records.loc[records["plant"] == plant_name].sort_values(
            "period"
        )
        axis.plot(
            plant_records["period"], plant_records["total_inflow_m3s"], label="Chegada"
        )
        axis.plot(
            plant_records["period"],
            plant_records["turbine_flow_m3s"],
            label="Turbinada",
        )
        axis.plot(
            plant_records["period"], plant_records["spill_flow_m3s"], label="Vertimento"
        )
        axis.set(
            title=f"Vazões — {scenario_name}, usina {plants[plant_name].name}",
            ylabel="m³/s",
        )
        axis.legend(loc=UPPER_RIGHT_LEGEND)
    axes[-1].set(xlabel=PERIOD_LABEL)
    figure.tight_layout()
    path = figures_dir / f"{slug}_flows.png"
    figure.savefig(path, dpi=160)
    plt.close(figure)
    return path


def _render_levels(
    records: pd.DataFrame,
    plants: dict[str, PlantConfig],
    figures_dir: Path,
    scenario_name: str,
    slug: str,
) -> Path:
    """Render upstream levels and operating limits for both plants."""
    figure, axes = plt.subplots(2, 1, figsize=(14, 6.5), sharex=True)
    for axis, plant_name in zip(axes, ("A", "B"), strict=True):
        plant_records = records.loc[records["plant"] == plant_name].sort_values(
            "period"
        )
        periods = plant_records["period"].to_list()
        levels = [plant_records.iloc[0]["initial_upstream_level_m"]]
        levels.extend(plant_records["final_upstream_level_m"].to_list())
        plant = plants[plant_name]
        axis.plot(range(len(levels)), levels, marker="o", label="Montante")
        axis.axhline(
            plant.min_level_m, color="#d62728", linestyle="--", label="Limite inferior"
        )
        axis.axhline(
            plant.max_level_m, color="#d62728", linestyle="--", label="Limite superior"
        )
        axis.set(
            title=f"Nível de montante — {scenario_name}, usina {plant.name}",
            ylabel="m",
            xticks=range(len(periods) + 1),
        )
        axis.legend(loc=UPPER_RIGHT_LEGEND)
    axes[-1].set(xlabel=PERIOD_LABEL)
    figure.tight_layout()
    path = figures_dir / f"{slug}_levels.png"
    figure.savefig(path, dpi=160)
    plt.close(figure)
    return path


def _scenario_slug(scenario_name: str) -> str:
    """Return a filesystem-safe, deterministic figure-name prefix."""
    return re.sub(r"[^a-z0-9]+", "_", scenario_name.lower()).strip("_")
