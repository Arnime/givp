"""Creation of reproducible synthetic hydropower benchmark artifacts."""

from __future__ import annotations

from collections.abc import Mapping
from hashlib import sha256
from pathlib import Path

from givp.examples.synthetic_hydropower.benchmark.artifacts import (
    BENCHMARK_SCHEMA_VERSION,
    OPTIMIZATION_MANIFEST_FILENAME,
    BenchmarkArtifacts,
)
from givp.examples.synthetic_hydropower.benchmark.frames import (
    _summary_frame,
    _time_series_frame,
)
from givp.examples.synthetic_hydropower.benchmark.storage import (
    _write_csv_atomic,
    _write_json_atomic,
)
from givp.examples.synthetic_hydropower.model import CascadeConfig, SimulationResult


def save_benchmark_results(
    results: Mapping[str, SimulationResult],
    cascade: CascadeConfig,
    scenario_seeds: Mapping[str, int],
    output_dir: Path,
    config_path: Path,
) -> BenchmarkArtifacts:
    """Save summary, time-series and provenance artifacts for benchmark results."""
    missing_seeds = set(results).difference(scenario_seeds)
    if missing_seeds:
        names = ", ".join(sorted(missing_seeds))
        raise ValueError(f"missing seeds for scenarios: {names}")

    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "optimization_summary.csv"
    time_series_path = output_dir / "optimization_time_series.csv"
    manifest_path = output_dir / OPTIMIZATION_MANIFEST_FILENAME

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
