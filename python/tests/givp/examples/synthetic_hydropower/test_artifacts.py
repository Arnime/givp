"""Tests for synthetic hydropower benchmark artifact persistence."""

import json
from hashlib import sha256
from pathlib import Path

import numpy as np
import pytest

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


def _write_promotion_source(
    output_dir: Path,
    config_path: Path,
    *,
    config_hash: str | None = None,
    include_results: bool = True,
) -> None:
    """Write the minimal optimization artifact set accepted by promotion."""
    output_dir.mkdir(parents=True, exist_ok=True)
    expected_hash = config_hash or sha256(config_path.read_bytes()).hexdigest()
    (output_dir / "protocol_manifest.json").write_text(
        json.dumps({"config_sha256": expected_hash}),
        encoding="utf-8",
    )
    if include_results:
        (output_dir / "optimization_summary.csv").write_text(
            "scenario\n",
            encoding="utf-8",
        )
        (output_dir / "optimization_time_series.csv").write_text(
            "scenario,period\n",
            encoding="utf-8",
        )


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
    for artifact_path in (
        artifacts.summary_path,
        artifacts.time_series_path,
        artifacts.manifest_path,
    ):
        assert b"\r\n" not in artifact_path.read_bytes()


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


def test_promotion_requires_a_manifest(tmp_path: Path) -> None:
    """Reject an output directory that has no auditable manifest."""
    config_path = tmp_path / "base.json"
    config_path.write_text("{}", encoding="utf-8")

    with pytest.raises(FileNotFoundError, match="missing benchmark manifest"):
        promote_benchmark_version(
            tmp_path / "output",
            tmp_path / "benchmarks" / "v1.0.0",
            config_path,
        )


def test_promotion_rejects_a_configuration_checksum_mismatch(
    tmp_path: Path,
) -> None:
    """Reject results generated from a different plant configuration."""
    config_path = tmp_path / "base.json"
    config_path.write_text("{}", encoding="utf-8")
    output_dir = tmp_path / "output"
    _write_promotion_source(output_dir, config_path, config_hash="not-the-checksum")

    with pytest.raises(ValueError, match="do not match"):
        promote_benchmark_version(
            output_dir,
            tmp_path / "benchmarks" / "v1.0.0",
            config_path,
        )


def test_promotion_does_not_overwrite_an_existing_protocol(tmp_path: Path) -> None:
    """Keep an already promoted protocol immutable."""
    config_path = tmp_path / "base.json"
    config_path.write_text("{}", encoding="utf-8")
    output_dir = tmp_path / "output"
    _write_promotion_source(output_dir, config_path)
    version_dir = tmp_path / "benchmarks" / "v1.0.0"
    (version_dir / "protocols" / "givp_optimization").mkdir(parents=True)

    with pytest.raises(FileExistsError, match="already exists"):
        promote_benchmark_version(output_dir, version_dir, config_path)


def test_promotion_requires_all_reference_results(tmp_path: Path) -> None:
    """Reject a partial run instead of publishing an incomplete benchmark."""
    config_path = tmp_path / "base.json"
    config_path.write_text("{}", encoding="utf-8")
    output_dir = tmp_path / "output"
    _write_promotion_source(output_dir, config_path, include_results=False)

    with pytest.raises(FileNotFoundError, match="missing benchmark artifacts"):
        promote_benchmark_version(
            output_dir,
            tmp_path / "benchmarks" / "v1.0.0",
            config_path,
        )


def test_promotion_reuses_only_an_identical_shared_configuration(
    tmp_path: Path,
) -> None:
    """Reject a version directory containing a different shared configuration."""
    config_path = tmp_path / "base.json"
    config_path.write_text('{"source": "current"}', encoding="utf-8")
    output_dir = tmp_path / "output"
    _write_promotion_source(output_dir, config_path)
    version_dir = tmp_path / "benchmarks" / "v1.0.0"
    config_dir = version_dir / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "base.json").write_text(
        '{"source": "different"}',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="shared configuration"):
        promote_benchmark_version(output_dir, version_dir, config_path)
