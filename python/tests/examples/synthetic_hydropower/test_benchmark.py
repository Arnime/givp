"""Tests for benchmark result persistence."""

import json
from hashlib import sha256
from pathlib import Path

import numpy as np

from givp.examples.synthetic_hydropower.benchmark import (
    promote_benchmark_version,
    save_benchmark_results,
)
from givp.examples.synthetic_hydropower.model import (
    CascadeConfig,
    PlantConfig,
    simulate_cascade,
)
from givp.examples.synthetic_hydropower.paths import default_config_path


def test_save_benchmark_results_writes_auditable_artifacts(tmp_path: Path) -> None:
    """Persist summary, time series, seeds, and source configuration checksum."""
    config_path = default_config_path()
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    plants = tuple(PlantConfig(**plant) for plant in payload["plants"])
    cascade = CascadeConfig((plants[0], plants[1]), 3, 1.0, 1, 1000.0)
    result = simulate_cascade(cascade, np.zeros((2, 3)), np.zeros((2, 3)))

    artifacts = save_benchmark_results(
        {"dry_stable": result},
        cascade,
        {"dry_stable": 42},
        tmp_path / "output",
        config_path,
    )

    assert artifacts.summary_path.is_file()
    assert artifacts.time_series_path.is_file()
    manifest = json.loads(artifacts.manifest_path.read_text(encoding="utf-8"))
    assert manifest["scenario_seeds"] == {"dry_stable": 42}
    assert manifest["saved_scenarios"] == ["dry_stable"]
    assert len(artifacts.time_series_path.read_text(encoding="utf-8").splitlines()) == 7


def test_promote_benchmark_version_freezes_matching_artifacts(tmp_path: Path) -> None:
    """Copy a complete local run only when its configuration checksum matches."""
    config_path = tmp_path / "base.json"
    config_path.write_text('{"plants": []}', encoding="utf-8")
    source_dir = tmp_path / "output"
    source_dir.mkdir()
    source_hash = sha256(config_path.read_bytes()).hexdigest()
    (source_dir / "protocol_manifest.json").write_text(
        json.dumps({"config_sha256": source_hash}), encoding="utf-8"
    )
    (source_dir / "optimization_summary.csv").write_text("scenario\n", encoding="utf-8")
    (source_dir / "optimization_time_series.csv").write_text(
        "scenario,period\n", encoding="utf-8"
    )

    version_dir = tmp_path / "benchmarks" / "v1.0.0"
    promote_benchmark_version(source_dir, version_dir, config_path)

    assert (version_dir / "config" / "base.json").is_file()
    assert (
        version_dir
        / "protocols"
        / "givp_optimization"
        / "reference_results"
        / "optimization_summary.csv"
    ).is_file()
