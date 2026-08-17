#!/usr/bin/env python3
"""Check selective CI gates and always-reported language coverage checks."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXPECTATIONS = {
    ".github/workflows/ci-python.yml": ("python/src", "pyproject.toml", "source_changed"),
    ".github/workflows/ci-rust.yml": ("rust/src", "rust/Cargo.toml", "source_changed"),
    ".github/workflows/ci-julia.yml": ("julia/src", "julia/Project.toml", "source_changed"),
    ".github/workflows/ci-r.yml": ("r/R", "r/DESCRIPTION", "source_changed"),
    ".github/workflows/ci-cpp.yml": ("cpp/include", "cpp/CMakeLists.txt", "source_changed"),
    ".github/workflows/codeql.yml": ("python/src/**", "poetry.lock"),
    ".github/workflows/security.yml": ("python/src/**", "poetry.lock"),
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
    if missing:
        raise SystemExit("\n".join(missing))
    print("PR CI path-filter checks passed.")


if __name__ == "__main__":
    main()
