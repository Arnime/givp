#!/usr/bin/env bash
# Build script for Cloudflare Pages (and local docs builds).
# Cloudflare build command: bash scripts/build-docs.sh
set -euo pipefail

REPOSITORY_ROOT="$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"

bash "$REPOSITORY_ROOT/.github/scripts/poetry-install.sh" --only main,docs
poetry -C "$REPOSITORY_ROOT/python" run mkdocs build \
    -f "$REPOSITORY_ROOT/mkdocs.yml" \
    --strict \
    --site-dir "$REPOSITORY_ROOT/site"
