"""Unit tests for the language-neutral hydropower protocol."""

from __future__ import annotations

import json
from dataclasses import fields
from io import StringIO

import numpy as np
import pandas as pd
import pytest

from givp.examples.synthetic_hydropower.interop import (
    PROTOCOL_VERSION,
    ProtocolError,
    canonical_cascade_config,
    evaluate_batch,
    parse_batch_request,
    run_worker,
)
from givp.examples.synthetic_hydropower.model import SimulationResult
from givp.examples.synthetic_hydropower.paths import project_root


def _zero_request(case_id: str = "zero") -> dict[str, object]:
    """Create the smallest valid canonical-horizon protocol batch."""
    return {
        "schema_version": PROTOCOL_VERSION,
        "requests": [
            {
                "case_id": case_id,
                "incremental_inflow_m3s": [[0.0] * 24, [0.0] * 24],
                "target_power_mw": [[0.0] * 24, [0.0] * 24],
            }
        ],
    }


def test_batch_evaluation_returns_the_complete_power_and_hydraulic_result() -> None:
    """Expose every public PowerScheduleResult and SimulationResult field in JSON."""
    response = evaluate_batch(_zero_request())

    assert response["schema_version"] == PROTOCOL_VERSION
    result = response["results"][0]  # type: ignore[index]
    assert result["case_id"] == "zero"  # type: ignore[index]
    assert set(result["power"]) == {  # type: ignore[index]
        "target_power_mw",
        "delivered_power_mw",
        "power_deficit_mw",
        "dispatch_status",
    }
    simulation = result["simulation"]  # type: ignore[index]
    assert {field.name for field in fields(SimulationResult)} <= set(simulation)  # type: ignore[arg-type]
    assert simulation["power_mw"] == [[0.0] * 24, [0.0] * 24]  # type: ignore[index]
    assert len(simulation["volume_hm3"][0]) == 25  # type: ignore[index]
    assert np.allclose(simulation["upstream_arrival_m3s"][1], 0.0)  # type: ignore[index]
    assert np.allclose(simulation["mass_balance_residual_hm3"], 0.0)  # type: ignore[index]


@pytest.mark.parametrize(
    ("mutator", "message"),
    [
        (lambda payload: payload.update(schema_version="other/v1"), "schema_version"),
        (
            lambda payload: payload["requests"][0].update(case_id=""),  # type: ignore[index]
            "case_id",
        ),
        (
            lambda payload: payload["requests"][0].update(  # type: ignore[index]
                target_power_mw=[[0.0] * 23, [0.0] * 23]
            ),
            "shape",
        ),
        (
            lambda payload: payload["requests"][0].update(  # type: ignore[index]
                incremental_inflow_m3s=[[float("nan")] * 24, [0.0] * 24]
            ),
            "finite",
        ),
        (
            lambda payload: payload["requests"][0].update(  # type: ignore[index]
                target_power_mw=[[1.0] * 24, [0.0] * 24]
            ),
            "must be zero",
        ),
    ],
)
def test_protocol_rejects_invalid_batches(mutator: object, message: str) -> None:
    """Reject malformed, non-finite, and physically invalid schedule requests."""
    payload = _zero_request()
    mutator(payload)  # type: ignore[operator]

    with pytest.raises((ProtocolError, ValueError), match=message):
        parse_batch_request(payload, canonical_cascade_config())
        evaluate_batch(payload)


def test_worker_keeps_serving_after_a_protocol_error() -> None:
    """Return one JSON response per non-empty JSON line without terminating early."""
    input_stream = StringIO(
        '{"schema_version": "wrong"}\n' + json.dumps(_zero_request())
    )
    output_stream = StringIO()

    run_worker(input_stream, output_stream)

    error, success = [
        json.loads(line) for line in output_stream.getvalue().splitlines()
    ]
    assert error["error"]["code"] == "invalid_request"
    assert success["results"][0]["case_id"] == "zero"


def test_worker_reports_an_invalid_power_schedule_without_crashing() -> None:
    """Keep the persistent worker available when the physical model rejects a target."""
    invalid = _zero_request()
    invalid["requests"][0]["target_power_mw"][0][0] = 1.0  # type: ignore[index]
    output_stream = StringIO()

    run_worker(StringIO(json.dumps(invalid)), output_stream)

    response = json.loads(output_stream.getvalue())
    assert response["error"]["code"] == "evaluation_error"


def test_protocol_rejects_duplicate_case_identifiers() -> None:
    """Keep a batch result unambiguous for callers that match by case identifier."""
    payload = _zero_request()
    payload["requests"].append(payload["requests"][0])  # type: ignore[index]

    with pytest.raises(ProtocolError, match="unique"):
        parse_batch_request(payload, canonical_cascade_config())


@pytest.mark.benchmark_regression
def test_zero_schedule_response_is_an_exact_protocol_oracle() -> None:
    """Freeze the complete JSON response used by all language-client smoke tests."""
    expected_path = project_root() / "interop" / "v1" / "zero_schedule_response.json"

    assert evaluate_batch(_zero_request("zero_schedule")) == json.loads(
        expected_path.read_text(encoding="utf-8")
    )


@pytest.mark.benchmark_regression
def test_protocol_matches_a_frozen_deterministic_case_within_tolerance() -> None:
    """Keep the public JSON boundary aligned with the canonical 1.0.0 results."""
    version_dir = project_root() / "benchmarks" / "v1.0.0"
    protocol_dir = version_dir / "protocols" / "deterministic_balance"
    schedules = pd.read_csv(protocol_dir / "inputs" / "power_schedules.csv")
    inflows = pd.read_csv(version_dir / "inputs" / "inflows.csv")
    expected = pd.read_csv(
        protocol_dir / "reference_results" / "balance_time_series.csv"
    )
    case_id = "dry_stable__a_off__b_off"

    payload = {
        "schema_version": PROTOCOL_VERSION,
        "requests": [
            {
                "case_id": case_id,
                "incremental_inflow_m3s": [
                    inflows[
                        (inflows["scenario"] == "dry_stable")
                        & (inflows["plant"] == plant)
                    ]
                    .sort_values("period")["incremental_inflow_m3s"]
                    .tolist()
                    for plant in ("A", "B")
                ],
                "target_power_mw": [
                    schedules[
                        (schedules["case_id"] == case_id)
                        & (schedules["plant"] == plant)
                    ]
                    .sort_values("period")["target_power_mw"]
                    .tolist()
                    for plant in ("A", "B")
                ],
            }
        ],
    }
    response = evaluate_batch(payload)
    actual = response["results"][0]  # type: ignore[index]
    expected_case = expected[expected["case_id"] == case_id]

    for plant_index, plant in enumerate(("A", "B")):
        expected_plant = expected_case[expected_case["plant"] == plant].sort_values(
            "period"
        )
        assert np.allclose(
            actual["power"]["delivered_power_mw"][plant_index],  # type: ignore[index]
            expected_plant["delivered_power_mw"],
            atol=1e-6,
        )
        assert np.allclose(
            actual["simulation"]["volume_hm3"][plant_index][1:],  # type: ignore[index]
            expected_plant["final_volume_hm3"],
            atol=1e-6,
        )
