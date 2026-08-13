#!/usr/bin/env bash
# Prevent central action pins from being copied back into language/release workflows.
set -euo pipefail

readonly workflows=(
  .github/workflows/ci-python.yml
  .github/workflows/ci-rust.yml
  .github/workflows/ci-julia.yml
  .github/workflows/ci-r.yml
  .github/workflows/ci-cpp.yml
  .github/workflows/dry-run-crates.yml
  .github/workflows/release-cpp.yml
  .github/workflows/testpypi.yml
)

readonly forbidden='actions/setup-python@|dtolnay/rust-toolchain@|Swatinem/rust-cache@|julia-actions/setup-julia@|julia-actions/cache@|r-lib/actions/setup-r@|r-lib/actions/setup-r-dependencies@|softprops/action-gh-release@'

if matches="$(rg --line-number --regexp="$forbidden" "${workflows[@]}" || true)"; then
  if [[ -n "$matches" ]]; then
    echo "::error::Use a component from .github/actions instead of copying a centralized action pin:"
    echo "$matches"
    exit 1
  fi
fi

echo "Centralized GitHub Action pin check passed."
