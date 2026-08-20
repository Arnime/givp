"""Artifact names and result paths for the synthetic hydropower benchmark."""

from dataclasses import dataclass
from pathlib import Path

BENCHMARK_SCHEMA_VERSION = "1.0"
BENCHMARK_MANIFEST_FILENAME = "benchmark_manifest.json"
BENCHMARK_RESULT_FILENAMES = (
    "benchmark_summary.csv",
    "benchmark_time_series.csv",
    BENCHMARK_MANIFEST_FILENAME,
)


@dataclass(frozen=True)
class BenchmarkArtifacts:
    """Paths written for one complete or partial benchmark execution."""

    summary_path: Path
    time_series_path: Path
    manifest_path: Path
