"""Artifact names and result paths for the synthetic hydropower benchmark."""

from dataclasses import dataclass
from pathlib import Path

BENCHMARK_SCHEMA_VERSION = "1.0"
OPTIMIZATION_MANIFEST_FILENAME = "protocol_manifest.json"
OPTIMIZATION_RESULT_FILENAMES = (
    "optimization_summary.csv",
    "optimization_time_series.csv",
    OPTIMIZATION_MANIFEST_FILENAME,
)


@dataclass(frozen=True)
class BenchmarkArtifacts:
    """Paths written for one complete or partial benchmark execution."""

    summary_path: Path
    time_series_path: Path
    manifest_path: Path
