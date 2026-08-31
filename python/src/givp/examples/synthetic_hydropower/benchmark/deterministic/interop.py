"""Derived interoperability artifacts for the frozen deterministic protocol.

The benchmark reference CSV files are written once by the Python physical
implementation.  This module builds protocol requests from their frozen inputs
and transforms a JSON worker response back to the same tabular schema.  It is
therefore suitable for validating transport clients without creating competing
reference results for R, Julia, Rust, or C++.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import fields
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from givp.examples.synthetic_hydropower.benchmark.cases import PowerCase
from givp.examples.synthetic_hydropower.benchmark.deterministic.execution import (
    DeterministicRun,
)
from givp.examples.synthetic_hydropower.benchmark.deterministic.frames import (
    balance_summary_frame,
    balance_time_series_frame,
)
from givp.examples.synthetic_hydropower.interop import PROTOCOL_VERSION
from givp.examples.synthetic_hydropower.model import (
    CascadeConfig,
    PowerScheduleResult,
    SimulationResult,
)

_PLANT_NAMES = ("A", "B")
_SIMULATION_INTEGER_FIELDS = {"state_duration_hours"}
_SIMULATION_BOOLEAN_FIELDS = {"unit_on"}
_SIMULATION_SCALAR_FIELDS = {
    "energy_mwh",
    "unit_switch_penalty",
    "early_switch_penalty",
    "minimum_level_penalty",
    "maximum_level_penalty",
    "level_penalty",
    "objective",
}


def build_batch_request(
    inflows: pd.DataFrame,
    schedules: pd.DataFrame,
    periods: int,
) -> dict[str, object]:
    """Build one protocol batch from frozen long-format benchmark inputs."""
    cases = power_cases_from_schedule(schedules, periods)
    inflow_by_scenario = _inflow_arrays(inflows, periods)
    requests = [
        {
            "case_id": case.case_id,
            "incremental_inflow_m3s": inflow_by_scenario[case.scenario].tolist(),
            "target_power_mw": case.target_power_mw.tolist(),
        }
        for case in cases
    ]
    return {"schema_version": PROTOCOL_VERSION, "requests": requests}


def power_cases_from_schedule(
    schedules: pd.DataFrame, periods: int
) -> tuple[PowerCase, ...]:
    """Rehydrate ordered factorial cases from the frozen schedule table."""
    required = {"case_id", "scenario", "level_a", "level_b", "plant", "period", "target_power_mw"}
    _require_columns(schedules, required, "power schedule")
    cases: list[PowerCase] = []
    for case_id, subset in schedules.groupby("case_id", sort=False):
        metadata = subset[["scenario", "level_a", "level_b"]].drop_duplicates()
        if len(metadata) != 1:
            raise ValueError(f"case {case_id!r} has inconsistent metadata")
        target = _plant_period_matrix(subset, "target_power_mw", periods, str(case_id))
        row = metadata.iloc[0]
        cases.append(
            PowerCase(
                case_id=str(case_id),
                scenario=str(row["scenario"]),
                level_a=str(row["level_a"]),
                level_b=str(row["level_b"]),
                target_power_mw=target,
            )
        )
    if not cases:
        raise ValueError("power schedule must contain at least one case")
    return tuple(cases)


def run_from_worker_response(
    response: object,
    inflows: pd.DataFrame,
    schedules: pd.DataFrame,
    cascade: CascadeConfig,
) -> DeterministicRun:
    """Rehydrate a worker response into the canonical deterministic frames."""
    cases = power_cases_from_schedule(schedules, cascade.periods)
    result_payloads = _result_payloads(response)
    expected_cases = {case.case_id for case in cases}
    missing = expected_cases.difference(result_payloads)
    if missing:
        raise ValueError(f"worker response is missing cases: {sorted(missing)}")
    results = {
        case.case_id: _power_schedule_result(result_payloads[case.case_id])
        for case in cases
    }
    unexpected = set(result_payloads).difference(expected_cases)
    if unexpected:
        raise ValueError(f"worker response contains unknown cases: {sorted(unexpected)}")
    return DeterministicRun(
        inflows=_inflow_arrays(inflows, cascade.periods), cases=cases, results=results
    )


def write_interop_artifacts(
    response: object,
    inflows_path: Path,
    schedules_path: Path,
    cascade: CascadeConfig,
    output_dir: Path,
    decimal_places: int,
) -> dict[str, Path]:
    """Persist six-decimal derived result tables from one language response."""
    run = run_from_worker_response(
        response, pd.read_csv(inflows_path), pd.read_csv(schedules_path), cascade
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    frames = {
        "balance_time_series": balance_time_series_frame(
            run.cases, run.results, cascade
        ),
        "balance_summary": balance_summary_frame(run.cases, run.results, cascade),
    }
    paths: dict[str, Path] = {}
    for name, frame in frames.items():
        path = output_dir / f"{name}.csv"
        frame.to_csv(
            path,
            index=False,
            float_format=f"%.{decimal_places}f",
            lineterminator="\n",
        )
        paths[name] = path
    return paths


def compare_interop_artifacts(
    artifact_paths: Mapping[str, Path], reference_dir: Path, tolerance: float
) -> dict[str, dict[str, float | int | bool]]:
    """Compare derived tables to frozen references within the protocol tolerance."""
    report: dict[str, dict[str, float | int | bool]] = {}
    for name, candidate_path in artifact_paths.items():
        reference_path = reference_dir / candidate_path.name
        candidate = pd.read_csv(candidate_path)
        reference = pd.read_csv(reference_path)
        if list(candidate.columns) != list(reference.columns):
            raise ValueError(f"column schema differs for {name}")
        if candidate.shape != reference.shape:
            raise ValueError(f"row count differs for {name}")
        maximum_error = _maximum_numeric_error(candidate, reference)
        text_columns = candidate.select_dtypes(exclude=[np.number]).columns
        text_matches = bool(candidate[text_columns].equals(reference[text_columns]))
        report[name] = {
            "rows": len(candidate),
            "maximum_numeric_error": maximum_error,
            "text_columns_match": text_matches,
            "passed": text_matches and maximum_error <= tolerance,
        }
    return report


def _inflow_arrays(
    inflows: pd.DataFrame, periods: int
) -> dict[str, NDArray[np.float64]]:
    _require_columns(inflows, {"scenario", "plant", "period", "incremental_inflow_m3s"}, "inflow")
    arrays = {
        str(scenario): _plant_period_matrix(
            subset, "incremental_inflow_m3s", periods, str(scenario)
        )
        for scenario, subset in inflows.groupby("scenario", sort=False)
    }
    if not arrays:
        raise ValueError("inflow table must contain at least one scenario")
    return arrays


def _plant_period_matrix(
    frame: pd.DataFrame, value_column: str, periods: int, identifier: str
) -> NDArray[np.float64]:
    plant_values = [
        frame.loc[frame["plant"] == plant]
        .sort_values("period")[value_column]
        .to_numpy(dtype=np.float64)
        for plant in _PLANT_NAMES
    ]
    if any(values.size != periods for values in plant_values):
        raise ValueError(f"invalid plant-period matrix for {identifier!r}")
    return np.vstack(plant_values)


def _result_payloads(response: object) -> dict[str, Mapping[str, object]]:
    if not isinstance(response, dict):
        raise ValueError("worker response must be a JSON object")
    if response.get("schema_version") != PROTOCOL_VERSION:
        raise ValueError("worker response has an unsupported schema version")
    raw_results = response.get("results")
    if not isinstance(raw_results, list) or not raw_results:
        raise ValueError("worker response must contain results")
    results: dict[str, Mapping[str, object]] = {}
    for item in raw_results:
        if not isinstance(item, dict) or not isinstance(item.get("case_id"), str):
            raise ValueError("worker response contains an invalid result")
        case_id = item["case_id"]
        if case_id in results:
            raise ValueError(f"worker response duplicates case {case_id!r}")
        results[case_id] = cast(Mapping[str, object], item)
    return results


def _power_schedule_result(payload: Mapping[str, object]) -> PowerScheduleResult:
    power = _mapping_field(payload, "power")
    simulation = _mapping_field(payload, "simulation")
    simulation_values: dict[str, object] = {}
    for field in fields(SimulationResult):
        raw_value = simulation.get(field.name)
        if raw_value is None:
            raise ValueError(f"simulation is missing {field.name!r}")
        if field.name in _SIMULATION_SCALAR_FIELDS:
            simulation_values[field.name] = float(cast(float, raw_value))
        elif field.name in _SIMULATION_INTEGER_FIELDS:
            simulation_values[field.name] = np.asarray(raw_value, dtype=np.int_)
        elif field.name in _SIMULATION_BOOLEAN_FIELDS:
            simulation_values[field.name] = np.asarray(raw_value, dtype=np.bool_)
        else:
            simulation_values[field.name] = np.asarray(raw_value, dtype=np.float64)
    return PowerScheduleResult(
        simulation=SimulationResult(**cast(Any, simulation_values)),
        target_power_mw=np.asarray(power["target_power_mw"], dtype=np.float64),
        delivered_power_mw=np.asarray(power["delivered_power_mw"], dtype=np.float64),
        power_deficit_mw=np.asarray(power["power_deficit_mw"], dtype=np.float64),
        dispatch_status=np.asarray(power["dispatch_status"], dtype=np.str_),
    )


def _mapping_field(payload: Mapping[str, object], name: str) -> Mapping[str, object]:
    value = payload.get(name)
    if not isinstance(value, dict):
        raise ValueError(f"worker result is missing {name!r}")
    return cast(Mapping[str, object], value)


def _maximum_numeric_error(candidate: pd.DataFrame, reference: pd.DataFrame) -> float:
    numeric_columns = candidate.select_dtypes(include=[np.number]).columns
    if not len(numeric_columns):
        return 0.0
    differences = np.abs(
        candidate[numeric_columns].to_numpy(dtype=np.float64)
        - reference[numeric_columns].to_numpy(dtype=np.float64)
    )
    return float(np.max(differences))


def _require_columns(frame: pd.DataFrame, required: set[str], label: str) -> None:
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"{label} table is missing columns: {sorted(missing)}")
