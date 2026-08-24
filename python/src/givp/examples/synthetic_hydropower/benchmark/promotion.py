"""Promotion of local benchmark artifacts to immutable reference versions."""

import json
from hashlib import sha256
from pathlib import Path
from shutil import copy2

from givp.examples.synthetic_hydropower.benchmark.artifacts import (
    OPTIMIZATION_MANIFEST_FILENAME,
    OPTIMIZATION_RESULT_FILENAMES,
)


def promote_benchmark_version(
    output_dir: Path,
    version_dir: Path,
    config_path: Path,
) -> None:
    """Promote complete local artifacts to a new immutable benchmark version."""
    manifest_path = output_dir / OPTIMIZATION_MANIFEST_FILENAME
    if not manifest_path.is_file():
        raise FileNotFoundError(f"missing benchmark manifest: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    config_hash = sha256(config_path.read_bytes()).hexdigest()
    if manifest.get("config_sha256") != config_hash:
        raise ValueError("output artifacts do not match the configuration snapshot")

    protocol_dir = version_dir / "protocols" / "givp_optimization"
    results_dir = protocol_dir / "reference_results"
    if protocol_dir.exists():
        raise FileExistsError(
            f"GIVP optimization protocol already exists: {protocol_dir}"
        )
    missing_artifacts = [
        filename
        for filename in OPTIMIZATION_RESULT_FILENAMES
        if not (output_dir / filename).is_file()
    ]
    if missing_artifacts:
        raise FileNotFoundError(
            f"missing benchmark artifacts: {', '.join(missing_artifacts)}"
        )

    config_dir = version_dir / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True)
    destination_config = config_dir / config_path.name
    if destination_config.is_file():
        if sha256(destination_config.read_bytes()).hexdigest() != config_hash:
            raise ValueError("existing shared configuration does not match the run")
    else:
        copy2(config_path, destination_config)
    for filename in OPTIMIZATION_RESULT_FILENAMES:
        destination = (
            protocol_dir / filename
            if filename == OPTIMIZATION_MANIFEST_FILENAME
            else results_dir / filename
        )
        copy2(output_dir / filename, destination)
