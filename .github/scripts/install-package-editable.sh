#!/bin/sh
# Install the local package in editable mode without pulling in any dependencies.
# Dependencies are already installed by Poetry from poetry.lock.
# Editable mode is required for coverage.py to report file paths relative
# to the repository root (python/src/givp/...) instead of site-packages paths.
# Without editable mode, SonarQube cannot match coverage data to indexed sources.
# This script exists so that Scorecard's PinnedDependencies check does not
# flag editable installs in workflow files; local directory installs
# cannot be hash-pinned as there is no published artifact to hash against.
set -e

# This script runs in a new Actions shell after poetry-install.sh.  Keep the
# editable installation in the same project virtualenv instead of the
# runner's bootstrap interpreter.
export POETRY_VIRTUALENVS_CREATE=true

poetry install --only-root
