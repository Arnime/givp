"""Persistence of deterministic artifacts for synthetic benchmark executions."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from shutil import copy2

import pandas as pd

from synthetic_hydropower.model import CascadeConfig, SimulationResult

BENCHMARK_SCHEMA_VERSION = "1.0"
BENCHMARK_MANIFEST_FILENAME = "benchmark_manifest.json"


@dataclass(frozen=True)
class BenchmarkArtifacts:
    """Paths written for one complete or partial benchmark execution."""

    summary_path: Path
    time_series_path: Path
    manifest_path: Path


BENCHMARK_RESULT_FILENAMES = (
    "benchmark_summary.csv",
    "benchmark_time_series.csv",
    BENCHMARK_MANIFEST_FILENAME,
)


def save_benchmark_results(
    results: Mapping[str, SimulationResult],
    cascade: CascadeConfig,
    scenario_seeds: Mapping[str, int],
    output_dir: Path,
    config_path: Path,
) -> BenchmarkArtifacts:
    """Save reproducible summary, time-series, and provenance artifacts.

    Args:
        results: Results already simulated or optimized, keyed by scenario name.
        cascade: Physical configuration that generated the results.
        scenario_seeds: Seed used for each saved scenario.
        output_dir: Explicit directory for local, ignored execution artifacts.
        config_path: Checked-in fictional plant configuration used by the run.

    Returns:
        Paths of the written CSV and JSON artifacts.

    Raises:
        ValueError: If a result has no corresponding recorded seed.
    """
    missing_seeds = set(results).difference(scenario_seeds)
    if missing_seeds:
        names = ", ".join(sorted(missing_seeds))
        raise ValueError(f"missing seeds for scenarios: {names}")

    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "benchmark_summary.csv"
    time_series_path = output_dir / "benchmark_time_series.csv"
    manifest_path = output_dir / BENCHMARK_MANIFEST_FILENAME

    _write_csv_atomic(_summary_frame(results, cascade, scenario_seeds), summary_path)
    _write_csv_atomic(
        _time_series_frame(results, cascade, scenario_seeds), time_series_path
    )
    manifest = {
        "schema_version": BENCHMARK_SCHEMA_VERSION,
        "config_file": config_path.name,
        "config_sha256": sha256(config_path.read_bytes()).hexdigest(),
        "periods": cascade.periods,
        "period_hours": cascade.period_hours,
        "travel_time_steps": cascade.travel_time_steps,
        "scenario_seeds": dict(scenario_seeds),
        "saved_scenarios": list(results),
        "artifacts": {
            "summary": summary_path.name,
            "time_series": time_series_path.name,
        },
    }
    _write_json_atomic(manifest, manifest_path)
    return BenchmarkArtifacts(summary_path, time_series_path, manifest_path)


def promote_benchmark_version(
    output_dir: Path,
    version_dir: Path,
    config_path: Path,
) -> None:
    """Promote complete local artifacts to a new immutable benchmark version.

    The source manifest must reference the exact configuration supplied for the
    release. An existing reference-results directory is never overwritten.

    Args:
        output_dir: Directory holding artifacts created by ``save_benchmark_results``.
        version_dir: Empty version directory such as ``benchmarks/v1.0.0``.
        config_path: Current fictional physical configuration to freeze.

    Raises:
        FileExistsError: If reference results already exist for the version.
        FileNotFoundError: If a required local artifact is missing.
        ValueError: If the local artifacts do not match the supplied configuration.
    """
    manifest_path = output_dir / BENCHMARK_MANIFEST_FILENAME
    if not manifest_path.is_file():
        raise FileNotFoundError(f"missing benchmark manifest: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    config_hash = sha256(config_path.read_bytes()).hexdigest()
    if manifest.get("config_sha256") != config_hash:
        raise ValueError("output artifacts do not match the configuration snapshot")

    results_dir = version_dir / "reference_results"
    if results_dir.exists():
        raise FileExistsError(
            f"benchmark reference results already exist: {results_dir}"
        )
    missing_artifacts = [
        filename
        for filename in BENCHMARK_RESULT_FILENAMES
        if not (output_dir / filename).is_file()
    ]
    if missing_artifacts:
        raise FileNotFoundError(
            f"missing benchmark artifacts: {', '.join(missing_artifacts)}"
        )

    config_dir = version_dir / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir()
    copy2(config_path, config_dir / config_path.name)
    for filename in BENCHMARK_RESULT_FILENAMES:
        copy2(output_dir / filename, results_dir / filename)


def _summary_frame(
    results: Mapping[str, SimulationResult],
    cascade: CascadeConfig,
    scenario_seeds: Mapping[str, int],
) -> pd.DataFrame:
    """Build one reproducible aggregate row for each scenario."""
    rows: list[dict[str, float | int | str]] = []
    for scenario_name, result in results.items():
        row: dict[str, float | int | str] = {
            "scenario": scenario_name,
            "seed": scenario_seeds[scenario_name],
            "energy_mwh": result.energy_mwh,
            "unit_switch_penalty": result.unit_switch_penalty,
            "early_switch_penalty": result.early_switch_penalty,
            "minimum_level_penalty": result.minimum_level_penalty,
            "maximum_level_penalty": result.maximum_level_penalty,
            "level_penalty": result.level_penalty,
            "objective": result.objective,
        }
        for plant_index, plant in enumerate(cascade.plants):
            plant_name = plant.name.lower()
            row[f"initial_level_{plant_name}_m"] = result.level_m[plant_index, 0]
            row[f"final_level_{plant_name}_m"] = result.level_m[plant_index, -1]
        rows.append(row)
    return pd.DataFrame(rows)


def _time_series_frame(
    results: Mapping[str, SimulationResult],
    cascade: CascadeConfig,
    scenario_seeds: Mapping[str, int],
) -> pd.DataFrame:
    """Build a long, tidy time-series table for all plants and scenarios."""
    rows: list[dict[str, float | int | str]] = []
    for scenario_name, result in results.items():
        for plant_index, plant in enumerate(cascade.plants):
            for period in range(cascade.periods):
                rows.append(
                    {
                        "scenario": scenario_name,
                        "seed": scenario_seeds[scenario_name],
                        "plant": plant.name,
                        "period": period,
                        "incremental_inflow_m3s": result.inflow_m3s[
                            plant_index, period
                        ],
                        "total_inflow_m3s": result.total_inflow_m3s[
                            plant_index, period
                        ],
                        "upstream_arrival_m3s": result.upstream_arrival_m3s[
                            plant_index, period
                        ],
                        "requested_flow_m3s": result.requested_flow_m3s[
                            plant_index, period
                        ],
                        "turbine_flow_m3s": result.turbine_flow_m3s[
                            plant_index, period
                        ],
                        "spill_flow_m3s": result.spill_flow_m3s[plant_index, period],
                        "sanitary_spill_flow_m3s": result.sanitary_spill_flow_m3s[
                            plant_index, period
                        ],
                        "capacity_spill_flow_m3s": result.capacity_spill_flow_m3s[
                            plant_index, period
                        ],
                        "level_control_spill_flow_m3s": result.level_control_spill_flow_m3s[
                            plant_index, period
                        ],
                        "defluent_flow_m3s": result.defluent_flow_m3s[
                            plant_index, period
                        ],
                        "initial_volume_hm3": result.volume_hm3[plant_index, period],
                        "final_volume_hm3": result.volume_hm3[plant_index, period + 1],
                        "initial_upstream_level_m": result.level_m[plant_index, period],
                        "final_upstream_level_m": result.level_m[
                            plant_index, period + 1
                        ],
                        "downstream_level_m": result.downstream_level_m[
                            plant_index, period
                        ],
                        "net_head_m": result.net_head_m[plant_index, period],
                        "power_mw": result.power_mw[plant_index, period],
                        "unit_on": result.unit_on[plant_index, period],
                        "state_duration_hours": result.state_duration_hours[
                            plant_index, period
                        ],
                        "unit_switch_penalty": result.unit_switch_penalty_by_period[
                            plant_index, period
                        ],
                        "early_switch_penalty": result.early_switch_penalty_by_period[
                            plant_index, period
                        ],
                        "minimum_level_penalty": result.minimum_level_penalty_by_period[
                            plant_index, period
                        ],
                        "maximum_level_penalty": result.maximum_level_penalty_by_period[
                            plant_index, period
                        ],
                    }
                )
    return pd.DataFrame(rows)


def _write_csv_atomic(dataframe: pd.DataFrame, path: Path) -> None:
    """Write a CSV through a temporary file to avoid partial artifacts."""
    temporary_path = path.with_suffix(".tmp")
    dataframe.to_csv(temporary_path, index=False)
    temporary_path.replace(path)


def _write_json_atomic(payload: object, path: Path) -> None:
    """Write JSON through a temporary file to avoid partial artifacts."""
    temporary_path = path.with_suffix(".tmp")
    temporary_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )
    temporary_path.replace(path)
