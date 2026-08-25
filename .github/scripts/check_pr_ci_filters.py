#!/usr/bin/env python3
"""Check selective CI gates and always-reported language coverage checks."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXPECTATIONS = {
    ".github/workflows/ci-python.yml": (
        "python/src",
        "python/pyproject.toml",
        "source_changed",
    ),
    ".github/workflows/ci-rust.yml": ("rust/src", "rust/Cargo.toml", "source_changed"),
    ".github/workflows/ci-julia.yml": (
        "julia/src",
        "julia/Project.toml",
        "source_changed",
    ),
    ".github/workflows/ci-r.yml": ("r/R", "r/DESCRIPTION", "source_changed"),
    ".github/workflows/ci-cpp.yml": (
        "cpp/include",
        "cpp/CMakeLists.txt",
        "source_changed",
    ),
    ".github/workflows/codeql.yml": ("python/src/**", "python/poetry.lock"),
    ".github/workflows/security.yml": ("python/src/**", "python/poetry.lock"),
}
ALWAYS_REPORTED_COVERAGE = {
    ".github/workflows/ci-python.yml": "Coverage not required for this pull request",
    ".github/workflows/ci-rust.yml": "name: coverage-rust",
    ".github/workflows/ci-julia.yml": "name: coverage-julia",
    ".github/workflows/ci-r.yml": "name: coverage-r",
    ".github/workflows/ci-cpp.yml": "name: coverage-cpp",
}
SLSA_WORKFLOWS = (
    ".github/workflows/release.yml",
    ".github/workflows/backfill-provenance.yml",
)


def _read(relative_path: str) -> str:
    """Read one repository file used by the CI contract checks."""
    return (ROOT / relative_path).read_text(encoding="utf-8")


def _check_expected_snippets() -> list[str]:
    """Return errors for missing language and security workflow markers."""
    errors: list[str] = []
    for relative_path, snippets in EXPECTATIONS.items():
        content = _read(relative_path)
        errors.extend(
            f"{relative_path}: missing {snippet!r}"
            for snippet in snippets
            if snippet not in content
        )
    return errors


def _check_coverage_contracts() -> list[str]:
    """Return errors when required coverage jobs can be skipped entirely."""
    errors: list[str] = []
    for relative_path, required_name in ALWAYS_REPORTED_COVERAGE.items():
        content = _read(relative_path)
        if "  pull_request:\n    paths:" in content:
            errors.append(f"{relative_path}: coverage must run on every PR")
        if required_name not in content:
            errors.append(f"{relative_path}: missing always-reported coverage check")
    return errors


def _check_codeql_pins() -> list[str]:
    """Return errors for missing or inconsistent immutable CodeQL pins."""
    codeql_pins = dict(
        re.findall(
            r"github/codeql-action/(init|analyze)@([0-9a-f]{40})",
            _read(".github/workflows/codeql.yml"),
        )
    )
    if set(codeql_pins) != {"init", "analyze"}:
        return [".github/workflows/codeql.yml: missing immutable init/analyze pins"]
    if len(set(codeql_pins.values())) != 1:
        return [".github/workflows/codeql.yml: init and analyze must use the same pin"]
    return []


def _check_slsa_pins() -> list[str]:
    """Return errors for absent or inconsistent SLSA generator pins."""
    errors: list[str] = []
    pins: list[str] = []
    pattern = (
        r"slsa-framework/slsa-github-generator/"
        r"\.github/workflows/generator_generic_slsa3\.yml@([0-9a-f]{40})"
    )
    for relative_path in SLSA_WORKFLOWS:
        match = re.search(pattern, _read(relative_path))
        if match is None:
            errors.append(f"{relative_path}: missing immutable SLSA generator pin")
        else:
            pins.append(match.group(1))
    if len(pins) == len(SLSA_WORKFLOWS) and len(set(pins)) != 1:
        errors.append(
            "SLSA generator pins must match in Release and Backfill Provenance"
        )
    return errors


def _missing_release_snippets(
    content: str, snippets: tuple[str, ...], message: str
) -> list[str]:
    """Return one formatted error for every absent release contract snippet."""
    return [
        message.format(snippet=snippet)
        for snippet in snippets
        if snippet not in content
    ]


def _check_python_release() -> list[str]:
    """Return errors when Python releases lose historical-layout support."""
    content = _read(".github/workflows/release.yml")
    errors: list[str] = []
    if "uses: ./.github/actions/setup-poetry" in content:
        errors.append("release.yml: historical tags cannot use the local Poetry action")
    if 'arnime.r-universe.dev/givp/json" | grep -q' in content:
        errors.append("release.yml: parse r-universe metadata as JSON instead of text")
    errors.extend(
        _missing_release_snippets(
            content,
            (
                "snok/install-poetry@a783c322200f0519c7926aa6faa857c4e23e9263",
                "[ -f python/pyproject.toml ]",
                "elif [ -f pyproject.toml ]",
                "mv dist python/dist",
                "json.load(sys.stdin)",
            ),
            "release.yml: missing historical Python layout support {snippet!r}",
        )
    )
    return errors


def _check_cpp_release() -> list[str]:
    """Return errors when C++ releases lose cross-platform or legacy support."""
    content = _read(".github/workflows/release-cpp.yml")
    errors: list[str] = []
    forbidden = {
        "python .github/scripts/validate_unified_version.py": (
            "release-cpp.yml: historical tags cannot use current local scripts"
        ),
        "--target RUN_TESTS": (
            "release-cpp.yml: use cross-platform ctest instead of RUN_TESTS"
        ),
    }
    errors.extend(
        message for snippet, message in forbidden.items() if snippet in content
    )
    errors.extend(
        _missing_release_snippets(
            content,
            (
                'Path("cpp/CMakeLists.txt")',
                "ctest --test-dir cpp/build/release-test --build-config Release",
                'CHANGELOG_PATH="docs/project/changelog.md"',
                'CHANGELOG_PATH="CHANGELOG.md"',
            ),
            "release-cpp.yml: missing historical layout support {snippet!r}",
        )
    )
    return errors


def main() -> None:
    """Fail when CI loses its selective validation or required-check contract."""
    checks = (
        _check_expected_snippets,
        _check_coverage_contracts,
        _check_codeql_pins,
        _check_slsa_pins,
        _check_python_release,
        _check_cpp_release,
    )
    missing = [error for check in checks for error in check()]
    if missing:
        raise SystemExit("\n".join(missing))
    print("PR CI path-filter checks passed.")


if __name__ == "__main__":
    main()
