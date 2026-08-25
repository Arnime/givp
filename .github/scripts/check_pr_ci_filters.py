#!/usr/bin/env python3
"""Check selective CI gates and always-reported language coverage checks."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXPECTATIONS = {
    ".github/workflows/ci-python.yml": ("python/src", "python/pyproject.toml", "source_changed"),
    ".github/workflows/ci-rust.yml": ("rust/src", "rust/Cargo.toml", "source_changed"),
    ".github/workflows/ci-julia.yml": ("julia/src", "julia/Project.toml", "source_changed"),
    ".github/workflows/ci-r.yml": ("r/R", "r/DESCRIPTION", "source_changed"),
    ".github/workflows/ci-cpp.yml": ("cpp/include", "cpp/CMakeLists.txt", "source_changed"),
    ".github/workflows/codeql.yml": ("python/src/**", "python/poetry.lock"),
    ".github/workflows/security.yml": ("python/src/**", "python/poetry.lock"),
}


def main() -> None:
    """Fail when CI loses its selective validation or required-check contract."""
    missing: list[str] = []
    for relative_path, snippets in EXPECTATIONS.items():
        content = (ROOT / relative_path).read_text(encoding="utf-8")
        for snippet in snippets:
            if snippet not in content:
                missing.append(f"{relative_path}: missing {snippet!r}")
    always_reported_coverage = {
        ".github/workflows/ci-python.yml": "Coverage not required for this pull request",
        ".github/workflows/ci-rust.yml": "name: coverage-rust",
        ".github/workflows/ci-julia.yml": "name: coverage-julia",
        ".github/workflows/ci-r.yml": "name: coverage-r",
        ".github/workflows/ci-cpp.yml": "name: coverage-cpp",
    }
    for relative_path, required_name in always_reported_coverage.items():
        content = (ROOT / relative_path).read_text(encoding="utf-8")
        if "  pull_request:\n    paths:" in content:
            missing.append(f"{relative_path}: coverage must run on every PR")
        if required_name not in content:
            missing.append(f"{relative_path}: missing always-reported coverage check")
    codeql_ci = (ROOT / ".github/workflows/codeql.yml").read_text(encoding="utf-8")
    codeql_pins = dict(
        re.findall(r"github/codeql-action/(init|analyze)@([0-9a-f]{40})", codeql_ci)
    )
    if set(codeql_pins) != {"init", "analyze"}:
        missing.append(".github/workflows/codeql.yml: missing immutable init/analyze pins")
    elif len(set(codeql_pins.values())) != 1:
        missing.append(".github/workflows/codeql.yml: init and analyze must use the same pin")
    slsa_pins: list[str] = []
    for relative_path in (
        ".github/workflows/release.yml",
        ".github/workflows/backfill-provenance.yml",
    ):
        content = (ROOT / relative_path).read_text(encoding="utf-8")
        match = re.search(
            r"slsa-framework/slsa-github-generator/"
            r"\.github/workflows/generator_generic_slsa3\.yml@([0-9a-f]{40})",
            content,
        )
        if match is None:
            missing.append(f"{relative_path}: missing immutable SLSA generator pin")
        else:
            slsa_pins.append(match.group(1))
    if len(slsa_pins) == 2 and len(set(slsa_pins)) != 1:
        missing.append("SLSA generator pins must match in Release and Backfill Provenance")
    release_ci = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
    if "uses: ./.github/actions/setup-poetry" in release_ci:
        missing.append("release.yml: historical tags cannot use the local Poetry action")
    for snippet in (
        "snok/install-poetry@a783c322200f0519c7926aa6faa857c4e23e9263",
        "[ -f python/pyproject.toml ]",
        "elif [ -f pyproject.toml ]",
        "mv dist python/dist",
    ):
        if snippet not in release_ci:
            missing.append(f"release.yml: missing historical Python layout support {snippet!r}")
    if missing:
        raise SystemExit("\n".join(missing))
    print("PR CI path-filter checks passed.")


if __name__ == "__main__":
    main()
