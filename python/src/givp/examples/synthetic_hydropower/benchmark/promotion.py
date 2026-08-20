"""Promotion of local benchmark artifacts to immutable reference versions."""

import json
from hashlib import sha256
from pathlib import Path
from shutil import copy2

from givp.examples.synthetic_hydropower.benchmark.artifacts import (
    BENCHMARK_MANIFEST_FILENAME,
    BENCHMARK_RESULT_FILENAMES,
)


def promote_benchmark_version(
    output_dir: Path,
    version_dir: Path,
    config_path: Path,
) -> None:
    """Promote complete local artifacts to a new immutable benchmark version."""
    manifest_path = output_dir / BENCHMARK_MANIFEST_FILENAME
    if not manifest_path.is_file():
        raise FileNotFoundError(f"missing benchmark manifest: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    config_hash = sha256(config_path.read_bytes()).hexdigest()
    if manifest.get("config_sha256") != config_hash:
        raise ValueError("output artifacts do not match the configuration snapshot")

    results_dir = version_dir / "reference_results"
    if results_dir.exists():
        raise FileExistsError(
            f"benchmark reference results already exist: {results_dir}"
        )
    missing_artifacts = [
        filename
        for filename in BENCHMARK_RESULT_FILENAMES
        if not (output_dir / filename).is_file()
    ]
    if missing_artifacts:
        raise FileNotFoundError(
            f"missing benchmark artifacts: {', '.join(missing_artifacts)}"
        )

    config_dir = version_dir / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir()
    copy2(config_path, config_dir / config_path.name)
    for filename in BENCHMARK_RESULT_FILENAMES:
        copy2(output_dir / filename, results_dir / filename)
