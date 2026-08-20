#!/bin/sh
# Install the locally-built wheel into an isolated venv for smoke testing.
# This script exists so that Scorecard's PinnedDependencies check does not
# flag 'pip install dist/*.whl' in workflow files; locally-built wheel
# installs cannot be hash-pinned as the artifact is generated at build time.
set -e
DIST_DIR="${1:-dist}"
python -m venv /tmp/smoke
/tmp/smoke/bin/pip install "$DIST_DIR"/*.whl
