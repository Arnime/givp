"""Shared optimisation adapter for the synthetic hydropower protocol."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from givp.examples.synthetic_hydropower.interop import PROTOCOL_VERSION, evaluate_batch

OPTIMIZATION_PROTOCOL_VERSION = "synthetic-hydropower/optimization-v1"


@dataclass(frozen=True)
class OptimizationDefinition:
    """Frozen cross-language controls for one hydropower optimisation run."""

    scenario: str
    seed: int
    periods: int
    minimum_power_mw: NDArray[np.float64]
    maximum_power_mw: NDArray[np.float64]
    incremental_inflow_m3s: NDArray[np.float64]
    optimizer: Mapping[str, object]

    @property
    def bounds(self) -> list[tuple[float, float]]:
        """Return the 48 raw-power bounds in canonical A-then-B order."""
        return [
            (0.0, float(self.maximum_power_mw[plant]))
            for plant in range(2)
            for _ in range(self.periods)
        ]


def load_optimization_definition(path: Path) -> OptimizationDefinition:
    """Load and validate the versioned cross-language optimisation definition."""
    payload: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("optimization definition must be a JSON object")
    if payload.get("schema_version") != OPTIMIZATION_PROTOCOL_VERSION:
        raise ValueError("unsupported optimization definition schema_version")
    periods = _positive_int(payload.get("periods"), "periods")
    scenario = payload.get("scenario")
    if not isinstance(scenario, str) or not scenario:
        raise ValueError("scenario must be a non-empty string")
    seed = _positive_int(payload.get("seed"), "seed", allow_zero=True)
    bounds = payload.get("power_bounds_mw")
    if not isinstance(bounds, dict):
        raise ValueError("power_bounds_mw must be an object")
    minimum = _vector(bounds.get("minimum"), "power_bounds_mw.minimum")
    maximum = _vector(bounds.get("maximum"), "power_bounds_mw.maximum")
    if np.any(minimum < 0.0) or np.any(maximum < minimum):
        raise ValueError("power bounds must satisfy 0 <= minimum <= maximum")
    inflow = _matrix(payload.get("incremental_inflow_m3s"), periods, "inflow")
    if np.any(inflow < 0.0):
        raise ValueError("inflow must be non-negative")
    optimizer = payload.get("optimizer")
    if not isinstance(optimizer, dict):
        raise ValueError("optimizer must be an object")
    return OptimizationDefinition(
        scenario=scenario,
        seed=seed,
        periods=periods,
        minimum_power_mw=minimum,
        maximum_power_mw=maximum,
        incremental_inflow_m3s=inflow,
        optimizer=optimizer,
    )


def project_power_vector(
    vector: NDArray[np.float64] | list[float], definition: OptimizationDefinition
) -> NDArray[np.float64]:
    """Project raw GIVP coordinates to zero or valid operating power."""
    values = np.asarray(vector, dtype=np.float64)
    if values.shape != (2 * definition.periods,):
        raise ValueError(f"power vector must contain {2 * definition.periods} values")
    if not np.all(np.isfinite(values)):
        raise ValueError("power vector must contain only finite values")
    schedule = values.reshape(2, definition.periods).copy()
    for plant in range(2):
        minimum = definition.minimum_power_mw[plant]
        maximum = definition.maximum_power_mw[plant]
        clipped = np.clip(schedule[plant], 0.0, maximum)
        schedule[plant] = np.where(clipped < minimum / 2.0, 0.0, clipped)
        schedule[plant] = np.where(
            (schedule[plant] > 0.0) & (schedule[plant] < minimum), minimum, schedule[plant]
        )
    return np.asarray(schedule, dtype=np.float64)


def make_optimization_request(
    vector: NDArray[np.float64] | list[float],
    definition: OptimizationDefinition,
    case_id: str = "optimization-candidate",
) -> dict[str, object]:
    """Build one valid physical request from a raw GIVP decision vector."""
    return {
        "schema_version": PROTOCOL_VERSION,
        "requests": [
            {
                "case_id": case_id,
                "incremental_inflow_m3s": definition.incremental_inflow_m3s.tolist(),
                "target_power_mw": project_power_vector(vector, definition).tolist(),
            }
        ],
    }


def evaluate_power_vector(
    vector: NDArray[np.float64] | list[float], definition: OptimizationDefinition
) -> tuple[float, dict[str, object]]:
    """Evaluate one projected schedule and return canonical objective and result."""
    response = evaluate_batch(make_optimization_request(vector, definition))
    result = _single_result(response)
    simulation = result["simulation"]
    if not isinstance(simulation, dict):
        raise RuntimeError("protocol response has no simulation payload")
    objective = simulation.get("objective")
    if not isinstance(objective, (int, float)) or not np.isfinite(objective):
        raise RuntimeError("protocol response has no finite objective")
    return float(objective), result


def summarize_result(result: Mapping[str, object]) -> dict[str, float]:
    """Extract language-neutral diagnostics from one protocol result."""
    simulation = result.get("simulation")
    power = result.get("power")
    if not isinstance(simulation, dict) or not isinstance(power, dict):
        raise ValueError("result must contain power and simulation payloads")
    return {
        "objective": _finite_scalar(simulation, "objective"),
        "energy_mwh": _finite_scalar(simulation, "energy_mwh"),
        "level_penalty": _finite_scalar(simulation, "level_penalty"),
        "unit_switch_penalty": _finite_scalar(simulation, "unit_switch_penalty"),
        "early_switch_penalty": _finite_scalar(simulation, "early_switch_penalty"),
        "power_deficit_mwh": float(np.sum(np.asarray(power["power_deficit_mw"], dtype=float))),
    }


def _single_result(response: Mapping[str, object]) -> dict[str, object]:
    results = response.get("results")
    if not isinstance(results, list) or len(results) != 1 or not isinstance(results[0], dict):
        raise RuntimeError("optimization protocol response must contain one result")
    return results[0]


def _finite_scalar(payload: Mapping[str, object], field: str) -> float:
    value = payload.get(field)
    if not isinstance(value, (int, float)) or not np.isfinite(value):
        raise ValueError(f"result field {field!r} must be finite")
    return float(value)


def _positive_int(value: object, field: str, *, allow_zero: bool = False) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or (value < 0 if allow_zero else value < 1):
        raise ValueError(f"{field} must be a positive integer")
    return value


def _vector(value: object, field: str) -> NDArray[np.float64]:
    array = np.asarray(value, dtype=np.float64)
    if array.shape != (2,) or not np.all(np.isfinite(array)):
        raise ValueError(f"{field} must contain two finite values")
    return array


def _matrix(value: object, periods: int, field: str) -> NDArray[np.float64]:
    array = np.asarray(value, dtype=np.float64)
    if array.shape != (2, periods) or not np.all(np.isfinite(array)):
        raise ValueError(f"{field} must have shape [2][{periods}] with finite values")
    return array
