#!/bin/sh
# Install the locally-built wheel into an isolated environment for smoke tests.
# Runtime dependencies and the wheel installer come from Poetry's hash-locked
# environment; the smoke step performs no package resolution over the network.
set -eu
DIST_DIR="${1:-dist}"
SMOKE_ENV="${SMOKE_ENV:-/tmp/smoke}"

set -- "$DIST_DIR"/*.whl
if [ "$#" -ne 1 ] || [ ! -f "$1" ]; then
  echo "Expected exactly one wheel in $DIST_DIR" >&2
  exit 1
fi

WHEEL_DIRECTORY="$(CDPATH= cd -- "$(dirname -- "$1")" && pwd)"
WHEEL_PATH="$WHEEL_DIRECTORY/$(basename -- "$1")"
POETRY_SITE_PACKAGES="$(poetry -C python run python -c 'from pathlib import Path; import installer; print(Path(installer.__file__).resolve().parent.parent)')"

python -m venv --clear "$SMOKE_ENV"
SMOKE_PYTHON="$SMOKE_ENV/bin/python"
if [ ! -x "$SMOKE_PYTHON" ]; then
  SMOKE_PYTHON="$SMOKE_ENV/Scripts/python.exe"
fi
SMOKE_PREFIX="$("$SMOKE_PYTHON" -c 'import sys; print(sys.prefix)')"
SMOKE_SITE_PACKAGES="$("$SMOKE_PYTHON" -c 'import sysconfig; print(sysconfig.get_path("purelib"))')"
printf '%s\n' "$POETRY_SITE_PACKAGES" > "$SMOKE_SITE_PACKAGES/poetry-dependencies.pth"

poetry -C python run python -m installer \
  --prefix "$SMOKE_PREFIX" \
  --validate-record all \
  "$WHEEL_PATH"
