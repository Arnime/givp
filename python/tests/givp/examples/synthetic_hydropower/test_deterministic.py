"""Regression tests for the frozen deterministic hydropower protocol."""

import json
from hashlib import sha256
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from givp.examples.synthetic_hydropower.benchmark import (
    load_deterministic_definition,
    load_frozen_inflows,
    run_deterministic_benchmark,
    save_deterministic_benchmark,
)
from givp.examples.synthetic_hydropower.benchmark.deterministic.interop import (
    build_batch_request,
    compare_interop_artifacts,
    run_from_worker_response,
    write_interop_artifacts,
)
from givp.examples.synthetic_hydropower.interop import (
    canonical_cascade_config,
    evaluate_batch,
)
from givp.examples.synthetic_hydropower.paths import (
    default_config_path,
    default_definition_path,
    project_root,
)


def _version_dir(version: str) -> Path:
    return project_root() / "benchmarks" / version


@pytest.mark.benchmark_regression
def test_canonical_dimensions_and_constant_schedules() -> None:
    """Freeze all seven scenarios and 36 constant schedules per scenario."""
    version_dir = _version_dir("v1.0.0")
    protocol_dir = version_dir / "protocols" / "deterministic_balance"
    inflows = pd.read_csv(version_dir / "inputs" / "inflows.csv")
    schedules = pd.read_csv(protocol_dir / "inputs" / "power_schedules.csv")
    results = pd.read_csv(
        protocol_dir / "reference_results" / "balance_time_series.csv"
    )
    summary = pd.read_csv(protocol_dir / "reference_results" / "balance_summary.csv")

    assert inflows.shape[0] == 336
    assert schedules.shape[0] == 12_096
    assert results.shape[0] == 12_096
    assert summary.shape[0] == 252
    assert inflows["scenario"].nunique() == 7
    assert schedules["case_id"].nunique() == 252
    per_schedule_values = schedules.groupby(["case_id", "plant"])[
        "target_power_mw"
    ].nunique()
    assert np.all(per_schedule_values.to_numpy() == 1)


@pytest.mark.benchmark_regression
def test_reexecution_has_identical_canonical_checksums(tmp_path: Path) -> None:
    """Recompute from frozen inputs and reproduce all four canonical CSVs."""
    source = _version_dir("v1.0.0")
    source_protocol = source / "protocols" / "deterministic_balance"
    definition = load_deterministic_definition(
        source / "config" / "base.json", source_protocol / "definition.json"
    )
    inflows = load_frozen_inflows(source / "inputs" / "inflows.csv", definition)
    run = run_deterministic_benchmark(definition, inflows)
    destination = tmp_path / "v1.0.0"
    (destination / "config").mkdir(parents=True)
    for relative in ("config/base.json", "data_provenance.json"):
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((source / relative).read_bytes())
    destination_definition = (
        destination / "protocols" / "deterministic_balance" / "definition.json"
    )
    destination_definition.parent.mkdir(parents=True, exist_ok=True)
    destination_definition.write_bytes(
        (source_protocol / "definition.json").read_bytes()
    )
    save_deterministic_benchmark(
        run,
        definition,
        destination,
        destination / "config" / "base.json",
        destination_definition,
        destination / "data_provenance.json",
    )
    for relative in (
        "inputs/inflows.csv",
        "protocols/deterministic_balance/inputs/power_schedules.csv",
        "protocols/deterministic_balance/reference_results/balance_time_series.csv",
        "protocols/deterministic_balance/reference_results/balance_summary.csv",
    ):
        assert (destination / relative).read_bytes() == (source / relative).read_bytes()


@pytest.mark.benchmark_regression
def test_single_version_manifest_covers_both_protocols() -> None:
    """Keep deterministic balance and GIVP optimization in one benchmark version."""
    version_dir = _version_dir("v1.0.0")
    manifest = json.loads(
        (version_dir / "benchmark_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["protocols"] == ["deterministic_balance", "givp_optimization"]
    for relative, expected_hash in manifest["checksums_sha256"].items():
        assert (
            sha256((version_dir / relative).read_bytes()).hexdigest() == expected_hash
        )


def test_deterministic_run_rejects_an_incomplete_scenario_mapping() -> None:
    """Require frozen inflows for every scenario and no unversioned additions."""
    definition = load_deterministic_definition(
        default_config_path(),
        default_definition_path().parent.parent
        / "deterministic_balance"
        / "definition.json",
    )

    with pytest.raises(ValueError, match="exactly the versioned scenarios"):
        run_deterministic_benchmark(definition, {"unexpected": np.zeros((2, 24))})


def test_frozen_inflow_loader_rejects_an_invalid_period_count(
    tmp_path: Path,
) -> None:
    """Reject a scenario table that cannot form two complete hourly series."""
    definition = load_deterministic_definition(
        default_config_path(),
        default_definition_path().parent.parent
        / "deterministic_balance"
        / "definition.json",
    )
    scenario_name = definition.scenarios[0].definition.name
    invalid_path = tmp_path / "inflows.csv"
    pd.DataFrame(
        [
            {
                "scenario": scenario_name,
                "plant": plant,
                "period": 0,
                "incremental_inflow_m3s": 1.0,
            }
            for plant in ("A", "B")
        ]
    ).to_csv(invalid_path, index=False)

    with pytest.raises(ValueError, match="invalid frozen inflow shape"):
        load_frozen_inflows(invalid_path, definition)


def test_deterministic_definition_requires_exactly_two_plants(
    tmp_path: Path,
) -> None:
    """Reject configuration snapshots that do not describe the two-plant cascade."""
    payload = json.loads(default_config_path().read_text(encoding="utf-8"))
    payload["plants"] = payload["plants"][:1]
    invalid_config = tmp_path / "base.json"
    invalid_config.write_text(json.dumps(payload), encoding="utf-8")
    definition_path = (
        default_definition_path().parent.parent
        / "deterministic_balance"
        / "definition.json"
    )

    with pytest.raises(ValueError, match="exactly two plants"):
        load_deterministic_definition(invalid_config, definition_path)


def test_interop_batch_reconstructs_all_frozen_cases() -> None:
    """Translate the immutable inputs into one ordered 252-case protocol batch."""
    version_dir = _version_dir("v1.0.0")
    protocol_dir = version_dir / "protocols" / "deterministic_balance"
    request = build_batch_request(
        pd.read_csv(version_dir / "inputs" / "inflows.csv"),
        pd.read_csv(protocol_dir / "inputs" / "power_schedules.csv"),
        periods=24,
    )

    assert request["schema_version"] == "synthetic-hydropower/v1"
    requests = request["requests"]
    assert isinstance(requests, list)
    assert len(requests) == 252
    assert requests[0]["case_id"] == "dry_stable__a_off__b_off"
    assert np.asarray(requests[-1]["target_power_mw"]).shape == (2, 24)


def test_interop_response_requires_every_scheduled_case() -> None:
    """Reject a transport response that silently omits a requested schedule."""
    version_dir = _version_dir("v1.0.0")
    protocol_dir = version_dir / "protocols" / "deterministic_balance"
    inflows = pd.read_csv(version_dir / "inputs" / "inflows.csv")
    schedules = pd.read_csv(protocol_dir / "inputs" / "power_schedules.csv")
    first_case = schedules["case_id"].iloc[0]
    response = evaluate_batch(
        build_batch_request(
            inflows,
            schedules[schedules["case_id"] == first_case],
            periods=24,
        )
    )

    with pytest.raises(ValueError, match="missing cases"):
        run_from_worker_response(
            response, inflows, schedules, canonical_cascade_config()
        )


@pytest.mark.integration
def test_worker_response_reproduces_the_frozen_deterministic_tables(
    tmp_path: Path,
) -> None:
    """Validate the Python worker path used by all non-Python clients."""
    version_dir = _version_dir("v1.0.0")
    protocol_dir = version_dir / "protocols" / "deterministic_balance"
    inflows_path = version_dir / "inputs" / "inflows.csv"
    schedules_path = protocol_dir / "inputs" / "power_schedules.csv"
    response = evaluate_batch(
        build_batch_request(
            pd.read_csv(inflows_path), pd.read_csv(schedules_path), periods=24
        )
    )

    artifacts = write_interop_artifacts(
        response,
        inflows_path,
        schedules_path,
        canonical_cascade_config(),
        tmp_path,
        decimal_places=6,
    )
    report = compare_interop_artifacts(
        artifacts, protocol_dir / "reference_results", tolerance=1e-6
    )

    assert all(item["passed"] for item in report.values())
    assert report["balance_time_series"]["rows"] == 12_096
    assert report["balance_summary"]["rows"] == 252
