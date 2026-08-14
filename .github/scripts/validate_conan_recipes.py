#!/usr/bin/env python3
"""Validate the ConanCenter GIVP recipe template kept in this repository."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

CANONICAL_URL = "https://github.com/Arnime/givp"
TARGET_NAME = "givp::givp"
PACKAGE_NAME = "givp"


def require(content: str, snippet: str, path: Path, errors: list[str]) -> None:
    """Record a missing required recipe contract snippet."""
    if snippet not in content:
        errors.append(f"{path}: missing {snippet!r}")


def read_template_version(config_path: Path) -> str:
    """Read the single active version declared by the CCI config file."""
    matches = re.findall(
        r'^\s*["\']?([0-9]+\.[0-9]+\.[0-9]+)["\']?:\s*\n\s+folder:\s+all\s*$',
        config_path.read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    if len(matches) != 1:
        raise ValueError(
            f"{config_path}: expected exactly one version mapped to the all folder."
        )
    return str(matches[0])


def main() -> None:
    """Check recipe metadata, target naming, and immutable source declaration."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True, help="Repository root")
    args = parser.parse_args()

    root = args.root.resolve()
    template_root = root / "cpp" / "conan" / "conancenter" / "recipes" / "givp"
    cci_recipe = template_root / "all" / "conanfile.py"
    conandata = template_root / "all" / "conandata.yml"
    test_cmake = template_root / "all" / "test_package" / "CMakeLists.txt"
    vcpkg_manifest = root / "cpp" / "vcpkg_ports" / "givp" / "vcpkg.json"
    vcpkg_portfile = vcpkg_manifest.with_name("portfile.cmake")

    template_version = read_template_version(template_root / "config.yml")
    errors: list[str] = []
    cci_content = cci_recipe.read_text(encoding="utf-8")
    conandata_content = conandata.read_text(encoding="utf-8")
    test_cmake_content = test_cmake.read_text(encoding="utf-8")
    vcpkg_manifest_content = vcpkg_manifest.read_text(encoding="utf-8")
    vcpkg_portfile_content = vcpkg_portfile.read_text(encoding="utf-8")

    require(cci_content, f'name = "{PACKAGE_NAME}"', cci_recipe, errors)
    require(cci_content, f'homepage = "{CANONICAL_URL}"', cci_recipe, errors)
    require(cci_content, "check_min_cppstd(self, 17)", cci_recipe, errors)
    require(cci_content, '"cmake_target_name", "givp::givp"', cci_recipe, errors)
    require(cci_content, 'package_type = "header-library"', cci_recipe, errors)
    require(
        test_cmake_content, "find_package(givp CONFIG REQUIRED)", test_cmake, errors
    )
    require(test_cmake_content, "givp::givp", test_cmake, errors)
    require(conandata_content, f'"{template_version}":', conandata, errors)
    require(
        conandata_content,
        f"https://github.com/Arnime/givp/archive/refs/tags/v{template_version}.tar.gz",
        conandata,
        errors,
    )
    if not re.search(r"sha256:\s*\"?[0-9a-f]{64}\"?", conandata_content):
        errors.append(f"{conandata}: missing a SHA256 source hash")
    require(vcpkg_manifest_content, '"name": "givp"', vcpkg_manifest, errors)
    require(
        vcpkg_manifest_content, f'"homepage": "{CANONICAL_URL}"', vcpkg_manifest, errors
    )
    require(
        vcpkg_manifest_content,
        f'"version": "{template_version}"',
        vcpkg_manifest,
        errors,
    )
    require(vcpkg_portfile_content, "REPO Arnime/givp", vcpkg_portfile, errors)
    require(vcpkg_portfile_content, "REF v${VERSION}", vcpkg_portfile, errors)
    require(vcpkg_portfile_content, "PACKAGE_NAME givp", vcpkg_portfile, errors)
    if not re.search(r"SHA512\s+[0-9a-f]{128}", vcpkg_portfile_content):
        errors.append(f"{vcpkg_portfile}: missing a SHA512 source hash")

    if errors:
        raise SystemExit("\n".join(errors))
    print(f"Conan recipe contracts are valid for givp/{template_version}.")


if __name__ == "__main__":
    main()
