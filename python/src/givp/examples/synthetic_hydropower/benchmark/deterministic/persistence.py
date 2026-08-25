"""Canonical persistence for the deterministic protocol and benchmark suite."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pandas as pd

from givp.examples.synthetic_hydropower.benchmark.definition import (
    DeterministicDefinition,
)
from givp.examples.synthetic_hydropower.benchmark.deterministic.execution import (
    DeterministicRun,
)
from givp.examples.synthetic_hydropower.benchmark.deterministic.frames import (
    balance_summary_frame,
    balance_time_series_frame,
    inflow_frame,
    schedule_frame,
)
from givp.examples.synthetic_hydropower.benchmark.storage import _write_json_atomic

DETERMINISTIC_PROTOCOL = "deterministic_balance"
ROOT_MANIFEST_FILENAME = "benchmark_manifest.json"
PROTOCOL_MANIFEST_FILENAME = "protocol_manifest.json"


def save_deterministic_benchmark(
    run: DeterministicRun,
    definition: DeterministicDefinition,
    benchmark_dir: Path,
    config_path: Path,
    definition_path: Path,
    provenance_path: Path,
) -> dict[str, str]:
    """Write canonical six-decimal CSVs and a checksum manifest."""
    paths = _artifact_paths(benchmark_dir)
    frames = {
        "inflows": inflow_frame(run.inflows),
        "power_schedules": schedule_frame(run.cases),
        "balance_time_series": balance_time_series_frame(
            run.cases, run.results, definition.cascade
        ),
        "balance_summary": balance_summary_frame(
            run.cases, run.results, definition.cascade
        ),
    }
    for name, frame in frames.items():
        _write_canonical_csv(frame, paths[name], definition.decimal_places)
    checksum_paths = [*paths.values(), config_path, definition_path, provenance_path]
    figures_dir = (
        benchmark_dir / "protocols" / DETERMINISTIC_PROTOCOL / "figures"
    )
    if figures_dir.is_dir():
        checksum_paths.extend(sorted(figures_dir.glob("*.png")))
    checksums = {
        str(path.relative_to(benchmark_dir)).replace("\\", "/"): _sha256(path)
        for path in checksum_paths
    }
    manifest = {
        "benchmark_id": definition.benchmark_id,
        "schema_version": "1.0.0/deterministic-balance",
        "decimal_places": definition.decimal_places,
        "comparison_tolerance": definition.comparison_tolerance,
        "scenario_count": len(definition.scenarios),
        "case_count": len(run.cases),
        "inflow_rows": len(frames["inflows"]),
        "power_schedule_rows": len(frames["power_schedules"]),
        "balance_time_series_rows": len(frames["balance_time_series"]),
        "balance_summary_rows": len(frames["balance_summary"]),
        "checksums_sha256": checksums,
    }
    protocol_dir = benchmark_dir / "protocols" / DETERMINISTIC_PROTOCOL
    _write_json_atomic(manifest, protocol_dir / PROTOCOL_MANIFEST_FILENAME)
    _write_suite_manifest(benchmark_dir)
    return checksums


def _artifact_paths(benchmark_dir: Path) -> dict[str, Path]:
    input_dir = benchmark_dir / "inputs"
    protocol_dir = benchmark_dir / "protocols" / DETERMINISTIC_PROTOCOL
    protocol_input_dir = protocol_dir / "inputs"
    result_dir = protocol_dir / "reference_results"
    input_dir.mkdir(parents=True, exist_ok=True)
    protocol_input_dir.mkdir(parents=True, exist_ok=True)
    result_dir.mkdir(parents=True, exist_ok=True)
    return {
        "inflows": input_dir / "inflows.csv",
        "power_schedules": protocol_input_dir / "power_schedules.csv",
        "balance_time_series": result_dir / "balance_time_series.csv",
        "balance_summary": result_dir / "balance_summary.csv",
    }


def _write_canonical_csv(frame: pd.DataFrame, path: Path, decimals: int) -> None:
    temporary = path.with_suffix(".tmp")
    frame.to_csv(
        temporary,
        index=False,
        float_format=f"%.{decimals}f",
        lineterminator="\n",
    )
    temporary.replace(path)


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _write_suite_manifest(benchmark_dir: Path) -> None:
    canonical_files = sorted(
        path
        for path in benchmark_dir.rglob("*")
        if path.is_file()
        and path.name != ROOT_MANIFEST_FILENAME
        and path.suffix.lower() in {".csv", ".json", ".png"}
    )
    protocols_dir = benchmark_dir / "protocols"
    protocol_names = sorted(
        path.name for path in protocols_dir.iterdir() if path.is_dir()
    )
    manifest = {
        "benchmark_id": "synthetic-hydropower-v1.0.0",
        "schema_version": "1.0.0",
        "protocols": protocol_names,
        "checksums_sha256": {
            str(path.relative_to(benchmark_dir)).replace("\\", "/"): _sha256(path)
            for path in canonical_files
        },
    }
    _write_json_atomic(manifest, benchmark_dir / ROOT_MANIFEST_FILENAME)
