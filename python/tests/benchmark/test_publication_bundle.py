"""Tests for the immutable hydropower publication-package generator."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from zipfile import ZipFile


def test_publication_bundle_uses_one_verified_git_revision(tmp_path: Path) -> None:
    """Create source and hydro archives without including local runtime artefacts."""

    repository_root = Path(__file__).resolve().parents[3]
    script = (
        repository_root
        / "experiments"
        / "synthetic_hydropower"
        / "scripts"
        / "create_publication_bundle.py"
    )
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--repository-root",
            str(repository_root),
            "--version",
            "v1.0.0",
            "--output-dir",
            str(tmp_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    metadata = json.loads((tmp_path / "publication.json").read_text(encoding="utf-8"))
    checksum_lines = (tmp_path / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    archives = sorted(tmp_path.glob("*.zip"))

    assert "verified" in result.stdout
    assert len(archives) == 2
    assert len(checksum_lines) == 2
    assert metadata["benchmark_id"] == "synthetic-hydropower-v1.0.0"
    assert metadata["verified_manifest_files"] > 0
    assert len(metadata["git_commit"]) == 40

    with ZipFile(next(path for path in archives if "source" in path.name)) as archive:
        names = archive.namelist()
    assert not any("/.venv/" in name for name in names)
    assert not any("/output/" in name for name in names)
