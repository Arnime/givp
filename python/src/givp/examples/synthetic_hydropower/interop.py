"""Versioned JSON interoperability boundary for the synthetic cascade model."""

from __future__ import annotations

import json
from dataclasses import dataclass, fields
from importlib.resources import files
from typing import Any, TextIO, cast

import numpy as np
from numpy.typing import NDArray

from givp.examples.synthetic_hydropower.model import (
    CascadeConfig,
    PlantConfig,
    PowerScheduleResult,
    simulate_power_schedule,
)

PROTOCOL_VERSION = "synthetic-hydropower/v1"
_PACKAGE_NAME = "givp.examples.synthetic_hydropower"


class ProtocolError(ValueError):
    """Raised when a JSON request violates the interoperability contract."""


@dataclass(frozen=True)
class PowerScheduleRequest:
    """One identified power-schedule evaluation received through the protocol."""

    case_id: str
    incremental_inflow_m3s: NDArray[np.float64]
    target_power_mw: NDArray[np.float64]


def canonical_cascade_config() -> CascadeConfig:
    """Load the immutable two-plant configuration bundled with the package."""
    plants_payload = _load_resource_json("base.json")["plants"]
    cascade_payload = _load_resource_json("canonical_protocol.json")["cascade"]
    plants = tuple(PlantConfig(**plant) for plant in plants_payload)
    if len(plants) != 2:
        raise RuntimeError(
            "the packaged canonical configuration must define two plants"
        )
    return CascadeConfig(plants=(plants[0], plants[1]), **cascade_payload)


def evaluate_batch(payload: object) -> dict[str, object]:
    """Evaluate a protocol batch with the canonical physical configuration."""
    config = canonical_cascade_config()
    requests = parse_batch_request(payload, config)
    return {
        "schema_version": PROTOCOL_VERSION,
        "results": [
            _serialize_result(
                request.case_id, _evaluate_request(config, request), config
            )
            for request in requests
        ],
    }


def parse_batch_request(
    payload: object, config: CascadeConfig
) -> tuple[PowerScheduleRequest, ...]:
    """Validate and convert one JSON batch into numerical simulation inputs."""
    if not isinstance(payload, dict):
        raise ProtocolError("request must be a JSON object")
    if payload.get("schema_version") != PROTOCOL_VERSION:
        raise ProtocolError(f"schema_version must be {PROTOCOL_VERSION!r}")
    raw_requests = payload.get("requests")
    if not isinstance(raw_requests, list) or not raw_requests:
        raise ProtocolError("requests must be a non-empty JSON array")
    requests = tuple(_parse_request(item, config) for item in raw_requests)
    case_ids = [request.case_id for request in requests]
    if len(case_ids) != len(set(case_ids)):
        raise ProtocolError("each case_id must be unique within a batch")
    return requests


def run_worker(input_stream: TextIO, output_stream: TextIO) -> None:
    """Serve newline-delimited protocol batches until the input stream closes."""
    for line in input_stream:
        if not line.strip():
            continue
        response = _evaluate_worker_line(line)
        output_stream.write(json.dumps(response, allow_nan=False) + "\n")
        output_stream.flush()


def _load_resource_json(filename: str) -> dict[str, Any]:
    resource = files(_PACKAGE_NAME).joinpath("configs").joinpath(filename)
    return cast(dict[str, Any], json.loads(resource.read_text(encoding="utf-8")))


def _parse_request(payload: object, config: CascadeConfig) -> PowerScheduleRequest:
    if not isinstance(payload, dict):
        raise ProtocolError("each request must be a JSON object")
    case_id = payload.get("case_id")
    if not isinstance(case_id, str) or not case_id.strip():
        raise ProtocolError("case_id must be a non-empty string")
    return PowerScheduleRequest(
        case_id=case_id,
        incremental_inflow_m3s=_parse_matrix(
            payload.get("incremental_inflow_m3s"),
            "incremental_inflow_m3s",
            config.periods,
        ),
        target_power_mw=_parse_matrix(
            payload.get("target_power_mw"), "target_power_mw", config.periods
        ),
    )


def _parse_matrix(value: object, field_name: str, periods: int) -> NDArray[np.float64]:
    try:
        matrix = np.asarray(value, dtype=np.float64)
    except (TypeError, ValueError) as error:
        raise ProtocolError(f"{field_name} must contain numeric values") from error
    if matrix.shape != (2, periods):
        raise ProtocolError(f"{field_name} must have shape [2][{periods}]")
    if not np.all(np.isfinite(matrix)):
        raise ProtocolError(f"{field_name} must contain only finite values")
    if field_name == "incremental_inflow_m3s" and np.any(matrix < 0.0):
        raise ProtocolError("incremental_inflow_m3s must be non-negative")
    return matrix


def _evaluate_request(
    config: CascadeConfig, request: PowerScheduleRequest
) -> PowerScheduleResult:
    return simulate_power_schedule(
        config,
        request.incremental_inflow_m3s,
        request.target_power_mw,
    )


def _serialize_result(
    case_id: str, result: PowerScheduleResult, config: CascadeConfig
) -> dict[str, object]:
    return {
        "case_id": case_id,
        "power": {
            "target_power_mw": _json_value(result.target_power_mw),
            "delivered_power_mw": _json_value(result.delivered_power_mw),
            "power_deficit_mw": _json_value(result.power_deficit_mw),
            "dispatch_status": _json_value(result.dispatch_status),
        },
        "simulation": _serialize_simulation(result, config),
    }


def _serialize_simulation(
    result: PowerScheduleResult, config: CascadeConfig
) -> dict[str, object]:
    simulation = result.simulation
    values = {
        field.name: _json_value(getattr(simulation, field.name))
        for field in fields(simulation)
    }
    mass_balance_residual = np.diff(simulation.volume_hm3, axis=1) - (
        (simulation.total_inflow_m3s - simulation.defluent_flow_m3s)
        * config.flow_to_volume_hm3
    )
    values["mass_balance_residual_hm3"] = _json_value(mass_balance_residual)
    return values


def _json_value(value: object) -> object:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    return value


def _evaluate_worker_line(line: str) -> dict[str, object]:
    try:
        return evaluate_batch(json.loads(line))
    except json.JSONDecodeError as error:
        return _error_response("invalid_json", error.msg)
    except ProtocolError as error:
        return _error_response("invalid_request", str(error))
    except (RuntimeError, ValueError) as error:
        return _error_response("evaluation_error", str(error))


def _error_response(code: str, message: str) -> dict[str, object]:
    return {
        "schema_version": PROTOCOL_VERSION,
        "error": {"code": code, "message": message},
    }
