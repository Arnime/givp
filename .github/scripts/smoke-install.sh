#!/bin/sh
# Install the locally-built wheel into an isolated venv for smoke testing.
# Dependencies and the wheel installer come from Poetry's hash-locked
# environment; the smoke step performs no package resolution over the network.
set -eu
DIST_DIR="${1:-dist}"
python -m venv --system-site-packages /tmp/smoke

set -- "$DIST_DIR"/*.whl
if [ "$#" -ne 1 ] || [ ! -f "$1" ]; then
  echo "Expected exactly one wheel in $DIST_DIR" >&2
  exit 1
fi

/tmp/smoke/bin/python -m installer --validate-record all "$1"
