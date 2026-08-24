"""Regression tests for the frozen deterministic benchmark protocol."""

import json
from hashlib import sha256
from pathlib import Path

import numpy as np
import pandas as pd

from givp.examples.synthetic_hydropower.benchmark import (
    load_deterministic_definition,
    load_frozen_inflows,
    run_deterministic_benchmark,
    save_deterministic_benchmark,
)
from givp.examples.synthetic_hydropower.paths import project_root


def _version_dir(version: str) -> Path:
    return project_root() / "benchmarks" / version


def test_canonical_dimensions_and_constant_schedules() -> None:
    """Freeze all seven scenarios and 36 constant schedules per scenario."""
    version_dir = _version_dir("v1.0.0")
    protocol_dir = version_dir / "protocols" / "deterministic_balance"
    inflows = pd.read_csv(version_dir / "inputs" / "inflows.csv")
    schedules = pd.read_csv(protocol_dir / "inputs" / "power_schedules.csv")
    results = pd.read_csv(
        protocol_dir / "reference_results" / "balance_time_series.csv"
    )
    summary = pd.read_csv(
        protocol_dir / "reference_results" / "balance_summary.csv"
    )

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


def test_single_version_manifest_covers_both_protocols() -> None:
    """Keep deterministic balance and GIVP optimization in one benchmark version."""
    version_dir = _version_dir("v1.0.0")
    manifest = json.loads(
        (version_dir / "benchmark_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["protocols"] == ["deterministic_balance", "givp_optimization"]
    for relative, expected_hash in manifest["checksums_sha256"].items():
        assert sha256((version_dir / relative).read_bytes()).hexdigest() == expected_hash
