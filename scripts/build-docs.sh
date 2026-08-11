#!/usr/bin/env bash
# Build script for Cloudflare Pages (and local docs builds).
# Cloudflare build command: bash scripts/build-docs.sh
set -euo pipefail

bash .github/scripts/poetry-install.sh --only main,docs
poetry run mkdocs build --strict
