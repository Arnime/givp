#!/usr/bin/env bash
# Build script for Cloudflare Pages (and local docs builds).
# Cloudflare build command: bash scripts/build-docs.sh
set -euo pipefail

poetry install --no-root --with docs
bash .github/scripts/install-package.sh
poetry run mkdocs build --strict
