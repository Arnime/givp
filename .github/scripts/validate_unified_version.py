#!/usr/bin/env python3
"""Validate the shared release version across all GIVP package manifests."""

from __future__ import annotations

import argparse
import importlib
import re
import sys
from pathlib import Path
from typing import Any, Protocol, cast


class TomlReader(Protocol):
    """Minimal TOML reader interface shared by tomllib and tomli."""

    def loads(self, data: str, /, **kwargs: Any) -> dict[str, Any]:
        """Parse TOML content into a dictionary."""
        raise NotImplementedError


toml_reader: TomlReader
if sys.version_info >= (3, 11):
    toml_reader = cast(TomlReader, importlib.import_module("tomllib"))
else:
    toml_reader = cast(TomlReader, importlib.import_module("tomli"))


def read_unified_version(root: Path) -> str:
    """Return the common package version or raise when manifests differ.

    Args:
        root: Repository root containing the release manifests.

    Raises:
        ValueError: If a manifest version is missing or versions differ.
    """
    pyproject = toml_reader.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    julia = toml_reader.loads(
        (root / "julia" / "Project.toml").read_text(encoding="utf-8")
    )
    cargo_match = re.search(
        r'^version\s*=\s*"([^"]+)"',
        (root / "rust" / "Cargo.toml").read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    r_match = re.search(
        r"^Version:\s*([0-9A-Za-z.+-]+)\s*$",
        (root / "r" / "DESCRIPTION").read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    cmake_match = re.search(
        r"project\(\s*givp\s+VERSION\s+([0-9A-Za-z.+-]+)",
        (root / "cpp" / "CMakeLists.txt").read_text(encoding="utf-8"),
    )
    conan_config = root / "cpp" / "conan" / "conancenter" / "recipes" / "givp" / "config.yml"
    conan_versions = re.findall(
        r'^\s*["\']?([0-9]+\.[0-9]+\.[0-9]+)["\']?:\s*\n\s+folder:\s+all\s*$',
        conan_config.read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    conandata = conan_config.parent / "all" / "conandata.yml"
    conandata_versions = re.findall(
        r'^\s*["\']?([0-9]+\.[0-9]+\.[0-9]+)["\']?:\s*$',
        conandata.read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    if (
        not cargo_match
        or not r_match
        or not cmake_match
        or len(conan_versions) != 1
        or len(conandata_versions) != 1
    ):
        raise ValueError("Unable to read a version from a release manifest.")

    python_version = pyproject.get("project", {}).get("version")
    julia_version = julia.get("version")
    if not isinstance(python_version, str) or not isinstance(julia_version, str):
        raise ValueError("Unable to read a version from a release manifest.")

    versions = {
        "pyproject.toml": python_version,
        "julia/Project.toml": julia_version,
        "rust/Cargo.toml": cargo_match.group(1),
        "r/DESCRIPTION": r_match.group(1),
        "cpp/CMakeLists.txt": cmake_match.group(1),
        "cpp/conan/conancenter/recipes/givp/config.yml": conan_versions[0],
        "cpp/conan/conancenter/recipes/givp/all/conandata.yml": conandata_versions[0],
    }
    unique_versions = set(versions.values())
    if len(unique_versions) != 1:
        details = "\n".join(
            f"  - {path}: {version}" for path, version in versions.items()
        )
        raise ValueError(
            "Version mismatch across manifests. Bump all language manifests to "
            f"the same version.\n{details}"
        )
    return str(next(iter(unique_versions)))


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True, help="Repository root")
    return parser.parse_args()


def main() -> None:
    """Validate manifests and print the shared release version."""
    args = parse_args()
    print(read_unified_version(args.root))


if __name__ == "__main__":
    main()
