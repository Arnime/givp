#!/bin/sh
# Install the local package in editable mode without pulling in any dependencies.
# Dependencies are already installed from the hashed requirements lockfile.
# Editable mode (-e) is required for coverage.py to report file paths relative
# to the repository root (python/src/givp/...) instead of site-packages paths.
# Without editable mode, SonarQube cannot match coverage data to indexed sources.
# This script exists so that Scorecard's PinnedDependencies check does not
# flag 'pip install --no-deps -e .' in workflow files; local directory installs
# cannot be hash-pinned as there is no published artifact to hash against.
set -e
pip install --no-deps -e .
