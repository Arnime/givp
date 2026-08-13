#!/usr/bin/env python3
"""Check that language CI workflows keep their PR path filters and gates."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EXPECTATIONS = {
    ".github/workflows/ci-python.yml": ("python/src/**", "pyproject.toml", "source_changed"),
    ".github/workflows/ci-rust.yml": ("rust/src/**", "rust/Cargo.toml", "source_changed"),
    ".github/workflows/ci-julia.yml": ("julia/src/**", "julia/Project.toml", "source_changed"),
    ".github/workflows/ci-r.yml": ("r/R/**", "r/DESCRIPTION", "source_changed"),
    ".github/workflows/ci-cpp.yml": ("cpp/include/**", "cpp/CMakeLists.txt", "source_changed"),
    ".github/workflows/codeql.yml": ("python/src/**", "poetry.lock"),
    ".github/workflows/security.yml": ("python/src/**", "poetry.lock"),
}


def main() -> None:
    """Fail when a workflow loses its selective PR validation contract."""
    missing: list[str] = []
    for relative_path, snippets in EXPECTATIONS.items():
        content = (ROOT / relative_path).read_text(encoding="utf-8")
        for snippet in snippets:
            if snippet not in content:
                missing.append(f"{relative_path}: missing {snippet!r}")
    if missing:
        raise SystemExit("\n".join(missing))
    print("PR CI path-filter checks passed.")


if __name__ == "__main__":
    main()
