"""Create checksum-verified publication ZIPs from a committed repository snapshot."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from zipfile import ZipFile

BENCHMARK_ROOT = Path("experiments/synthetic_hydropower/benchmarks")
HYDROSHARE_PATHS = (
    "experiments/synthetic_hydropower/README.md",
    "experiments/synthetic_hydropower/benchmarks/README.md",
)
ZENODO_PATHS = (
    ".",
    ":(exclude)experiments/synthetic_hydropower/output",
    ":(exclude)experiments/synthetic_hydropower/publication",
)


@dataclass(frozen=True)
class PublicationArchive:
    """Description of one generated immutable publication file."""

    filename: str
    sha256: str
    bytes: int


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create Zenodo and HydroShare ZIPs from one Git revision."
    )
    parser.add_argument("--repository-root", required=True, type=Path)
    parser.add_argument("--version", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--revision", default="HEAD")
    return parser.parse_args()


def _run_git(repository_root: Path, *arguments: str) -> str:
    """Run a fixed Git command without invoking a shell."""

    git_executable = shutil.which("git")
    if git_executable is None:
        raise OSError("git executable was not found on PATH")
    result = subprocess.run(  # noqa: S603
        [git_executable, *arguments],
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _create_archive(
    repository_root: Path,
    revision: str,
    destination: Path,
    prefix: str,
    paths: tuple[str, ...] = (),
) -> None:
    command = [
        "archive",
        "--format=zip",
        f"--prefix={prefix}/",
        f"--output={destination}",
        revision,
    ]
    if paths:
        command.extend(("--", *paths))
    _run_git(repository_root, *command)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_frozen_manifest(archive: Path, prefix: str, version: str) -> int:
    benchmark_path = BENCHMARK_ROOT / version
    manifest_path = f"{prefix}/{benchmark_path.as_posix()}/benchmark_manifest.json"
    with ZipFile(archive) as bundle:
        manifest = json.loads(bundle.read(manifest_path))
        for relative_path, expected_hash in manifest["checksums_sha256"].items():
            archived_path = f"{prefix}/{benchmark_path.as_posix()}/{relative_path}"
            actual_hash = hashlib.sha256(bundle.read(archived_path)).hexdigest()
            if actual_hash != expected_hash:
                raise ValueError(
                    f"checksum mismatch for {relative_path}: "
                    f"expected {expected_hash}, got {actual_hash}"
                )
        return len(manifest["checksums_sha256"])


def _write_sidecars(
    output_directory: Path,
    revision: str,
    version: str,
    archives: tuple[PublicationArchive, ...],
    verified_files: int,
) -> None:
    checksums = "".join(f"{item.sha256}  {item.filename}\n" for item in archives)
    (output_directory / "SHA256SUMS").write_text(checksums, encoding="utf-8")
    payload = {
        "benchmark_id": f"synthetic-hydropower-{version}",
        "git_commit": revision,
        "archives": [asdict(item) for item in archives],
        "verified_manifest_files": verified_files,
    }
    (output_directory / "publication.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main() -> int:
    """Create and verify Zenodo and HydroShare publication archives."""

    arguments = _parse_arguments()
    repository_root = arguments.repository_root.resolve()
    output_directory = arguments.output_dir.resolve()
    benchmark_path = BENCHMARK_ROOT / arguments.version
    if not (repository_root / benchmark_path).is_dir():
        raise ValueError(f"benchmark version does not exist: {arguments.version}")

    revision = _run_git(
        repository_root,
        "rev-parse",
        "--verify",
        "--end-of-options",
        f"{arguments.revision}^{{commit}}",
    )
    short_revision = revision[:12]
    prefix = f"synthetic-hydropower-{arguments.version}"
    output_directory.mkdir(parents=True, exist_ok=True)

    zenodo_archive = output_directory / f"{prefix}-source-{short_revision}.zip"
    hydroshare_archive = output_directory / f"{prefix}-hydroshare-{short_revision}.zip"
    _create_archive(repository_root, revision, zenodo_archive, prefix, ZENODO_PATHS)
    _create_archive(
        repository_root,
        revision,
        hydroshare_archive,
        prefix,
        (*HYDROSHARE_PATHS, benchmark_path.as_posix()),
    )

    verified_files = _verify_frozen_manifest(zenodo_archive, prefix, arguments.version)
    hydroshare_verified = _verify_frozen_manifest(
        hydroshare_archive, prefix, arguments.version
    )
    archives = tuple(
        PublicationArchive(
            filename=archive.name,
            sha256=_sha256(archive),
            bytes=archive.stat().st_size,
        )
        for archive in (zenodo_archive, hydroshare_archive)
    )
    _write_sidecars(
        output_directory,
        revision,
        arguments.version,
        archives,
        min(verified_files, hydroshare_verified),
    )
    print(f"created {len(archives)} archives from {revision}")
    print(f"verified {verified_files} canonical benchmark files")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, subprocess.CalledProcessError, ValueError) as error:
        print(f"publication bundle failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
