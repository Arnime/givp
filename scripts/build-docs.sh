#!/usr/bin/env bash
# Build script for Cloudflare Pages (and local docs builds).
# Cloudflare build command: bash scripts/build-docs.sh
set -euo pipefail

pip install --require-hashes -r python/requirements/docs.txt
bash .github/scripts/install-package.sh
mkdocs build --strict
