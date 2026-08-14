#!/usr/bin/env python3
"""Copy a GIVP registry template and derive its immutable source hash."""

from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import subprocess
from pathlib import Path


def digest(path: Path, algorithm: str) -> str:
    """Return the hexadecimal digest for an already downloaded release archive."""
    hasher = hashlib.new(algorithm)
    with path.open("rb") as archive:
        for chunk in iter(lambda: archive.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def replace_hash(path: Path, algorithm: str, value: str) -> None:
    """Replace exactly one declared registry source hash in ``path``."""
    content = path.read_text(encoding="utf-8")
    pattern = rf"({algorithm}(?::\s*|\s+)[\"']?)[0-9a-f]{{{len(value)}}}([\"']?)"
    updated, replacements = re.subn(pattern, rf"\g<1>{value}\2", content, count=1)
    if replacements != 1:
        raise ValueError(f"{path}: expected exactly one {algorithm} hash")
    path.write_text(updated, encoding="utf-8")


def copy_template(source: Path, destination: Path) -> None:
    """Replace one generated registry directory with the versioned local template."""
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)


def sync_vcpkg(args: argparse.Namespace) -> None:
    """Sync the vcpkg port and regenerate its version database entry."""
    destination = args.fork / "ports" / "givp"
    copy_template(args.source / "cpp" / "vcpkg_ports" / "givp", destination)
    replace_hash(
        destination / "portfile.cmake", "SHA512", digest(args.archive, "sha512")
    )
    subprocess.run(  # noqa: S603 -- the workflow supplies the bootstrapped vcpkg executable.
        [str(args.vcpkg), "x-add-version", "givp", "--overwrite-version"],
        cwd=args.fork,
        check=True,
    )


def sync_conan(args: argparse.Namespace) -> None:
    """Sync the ConanCenter recipe and replace only its immutable SHA256."""
    destination = args.fork / "recipes" / "givp"
    copy_template(
        args.source / "cpp" / "conan" / "conancenter" / "recipes" / "givp",
        destination,
    )
    replace_hash(
        destination / "all" / "conandata.yml", "sha256", digest(args.archive, "sha256")
    )


def parse_args() -> argparse.Namespace:
    """Parse synchronization inputs supplied by the GitHub Actions workflow."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", choices=("vcpkg", "conan"), required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--fork", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--vcpkg", type=Path)
    return parser.parse_args()


def main() -> None:
    """Synchronize one external registry checkout from the local GIVP templates."""
    args = parse_args()
    if args.registry == "vcpkg":
        if args.vcpkg is None:
            raise ValueError("--vcpkg is required when synchronizing vcpkg")
        sync_vcpkg(args)
    else:
        sync_conan(args)


if __name__ == "__main__":
    main()
