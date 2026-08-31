"""Unit tests for deterministic protocol artifact conversion."""

from __future__ import annotations

import json
from collections.abc import Callable
from copy import deepcopy
from pathlib import Path
from typing import Any, cast

import pandas as pd
import pytest

from givp.examples.synthetic_hydropower.benchmark.deterministic.interop import (
    compare_interop_artifacts,
    power_cases_from_schedule,
    run_from_worker_response,
    write_interop_artifacts,
)
from givp.examples.synthetic_hydropower.interop import canonical_cascade_config
from givp.examples.synthetic_hydropower.paths import project_root


def _protocol_paths() -> tuple[Path, Path, Path]:
    """Return the frozen inputs and response used as a one-case unit fixture."""
    root = project_root()
    return (
        root / "benchmarks" / "v1.0.0" / "inputs" / "inflows.csv",
        root
        / "benchmarks"
        / "v1.0.0"
        / "protocols"
        / "deterministic_balance"
        / "inputs"
        / "power_schedules.csv",
        root / "interop" / "v1" / "zero_schedule_response.json",
    )


def _one_case_inputs() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
    """Load the smallest frozen transport fixture without running the model."""
    inflows_path, schedules_path, response_path = _protocol_paths()
    schedules = pd.read_csv(schedules_path)
    case_id = "dry_stable__a_off__b_off"
    one_schedule = schedules[schedules["case_id"] == case_id].copy()
    one_inflows = pd.read_csv(inflows_path)
    one_inflows = one_inflows[one_inflows["scenario"] == "dry_stable"].copy()
    response = json.loads(response_path.read_text(encoding="utf-8"))
    response["results"][0]["case_id"] = case_id  # type: ignore[index]
    return one_inflows, one_schedule, response


def test_rehydrates_one_frozen_worker_result_without_physical_execution() -> None:
    """Restore strongly typed results from a complete frozen JSON payload."""
    inflows, schedules, response = _one_case_inputs()

    run = run_from_worker_response(
        response, inflows, schedules, canonical_cascade_config()
    )

    assert tuple(run.results) == ("dry_stable__a_off__b_off",)
    result = run.results["dry_stable__a_off__b_off"]
    assert result.delivered_power_mw.shape == (2, 24)
    assert result.simulation.volume_hm3.shape == (2, 25)
    assert result.simulation.state_duration_hours.dtype.kind in {"i", "u"}
    assert result.simulation.unit_on.dtype.kind == "b"


def test_writes_and_compares_derived_artifacts_for_one_case(tmp_path: Path) -> None:
    """Write stable CSVs and compare them with an explicit local oracle."""
    inflows, schedules, response = _one_case_inputs()
    inflows_path = tmp_path / "inflows.csv"
    schedules_path = tmp_path / "power_schedules.csv"
    inflows.to_csv(inflows_path, index=False)
    schedules.to_csv(schedules_path, index=False)
    output_dir = tmp_path / "output"
    artifacts = write_interop_artifacts(
        response,
        inflows_path,
        schedules_path,
        canonical_cascade_config(),
        output_dir,
        decimal_places=6,
    )
    reference_dir = tmp_path / "reference"
    reference_dir.mkdir()
    for path in artifacts.values():
        (reference_dir / path.name).write_bytes(path.read_bytes())

    report = compare_interop_artifacts(artifacts, reference_dir, tolerance=1e-6)

    assert all(item["passed"] for item in report.values())
    assert report["balance_time_series"]["rows"] == 48
    assert report["balance_summary"]["rows"] == 1


@pytest.mark.parametrize(
    ("mutator", "message"),
    [
        (lambda response: response.update(schema_version="unsupported/v1"), "schema"),
        (lambda response: response.update(results=[]), "contain results"),
        (lambda response: response["results"].append(deepcopy(response["results"][0])), "duplicates"),  # type: ignore[index]
        (lambda response: response["results"][0].pop("power"), "missing 'power'"),  # type: ignore[index]
        (lambda response: response["results"][0]["simulation"].pop("volume_hm3"), "missing 'volume_hm3'"),  # type: ignore[index]
    ],
)
def test_rejects_invalid_worker_contracts(mutator: object, message: str) -> None:
    """Reject malformed result envelopes before derived data are written."""
    inflows, schedules, response = _one_case_inputs()
    mutator(response)  # type: ignore[operator]

    with pytest.raises(ValueError, match=message):
        run_from_worker_response(
            response, inflows, schedules, canonical_cascade_config()
        )


def test_rejects_bad_schedule_metadata_and_artifact_schema(tmp_path: Path) -> None:
    """Keep schedule and output validation independent from the worker process."""
    inflows, schedules, response = _one_case_inputs()
    inconsistent = pd.concat(
        [schedules, schedules.assign(level_a="other")], ignore_index=True
    )
    with pytest.raises(ValueError, match="inconsistent metadata"):
        power_cases_from_schedule(inconsistent, periods=24)

    artifacts = write_interop_artifacts(
        response,
        _write_frame(tmp_path / "inflows.csv", inflows),
        _write_frame(tmp_path / "schedules.csv", schedules),
        canonical_cascade_config(),
        tmp_path / "output",
        decimal_places=6,
    )
    reference_dir = tmp_path / "reference"
    reference_dir.mkdir()
    for path in artifacts.values():
        frame = pd.read_csv(path)
        frame.rename(columns={frame.columns[0]: "unexpected"}).to_csv(
            reference_dir / path.name, index=False
        )
    with pytest.raises(ValueError, match="column schema"):
        compare_interop_artifacts(artifacts, reference_dir, tolerance=1e-6)


@pytest.mark.parametrize(
    ("schedule", "message"),
    [
        (lambda frame: frame.iloc[0:0], "at least one case"),
        (lambda frame: frame.iloc[:-1], "invalid plant-period matrix"),
    ],
)
def test_rejects_empty_or_incomplete_power_schedules(
    schedule: Callable[[pd.DataFrame], pd.DataFrame], message: str
) -> None:
    """Reject schedule tables that cannot represent a complete hydraulic case."""
    _, schedules, _ = _one_case_inputs()

    with pytest.raises(ValueError, match=message):
        power_cases_from_schedule(schedule(schedules), periods=24)


def test_rejects_empty_inflows_and_unexpected_worker_cases() -> None:
    """Reject empty hydrology and result cases absent from the frozen schedule."""
    inflows, schedules, response = _one_case_inputs()
    with pytest.raises(ValueError, match="at least one scenario"):
        run_from_worker_response(
            response,
            inflows.iloc[0:0],
            schedules,
            canonical_cascade_config(),
        )

    response_with_extra_case = deepcopy(response)
    raw_results = cast(list[dict[str, Any]], response_with_extra_case["results"])
    extra_case = deepcopy(raw_results[0])
    extra_case["case_id"] = "unlisted-case"
    raw_results.append(extra_case)
    with pytest.raises(ValueError, match="unknown cases"):
        run_from_worker_response(
            response_with_extra_case,
            inflows,
            schedules,
            canonical_cascade_config(),
        )


def _write_frame(path: Path, frame: pd.DataFrame) -> Path:
    """Persist a temporary CSV fixture and return its explicit path."""
    frame.to_csv(path, index=False)
    return path
