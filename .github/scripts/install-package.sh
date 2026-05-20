#!/bin/sh
# Install the local package without pulling in any dependencies.
# Dependencies are already installed from the hashed requirements lockfile.
# Build a local wheel, hash it, and install through a one-line requirements file
# so Scorecard can verify the install is hash-pinned as well.
set -e

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT INT TERM

python -m build --wheel --outdir "$TMP_DIR" .
WHEEL_PATH="$(find "$TMP_DIR" -maxdepth 1 -name '*.whl' | head -n 1)"
WHEEL_HASH="$(sha256sum "$WHEEL_PATH" | awk '{print $1}')"
WHEEL_URL="$(python -c 'from pathlib import Path; import sys; print(Path(sys.argv[1]).resolve().as_uri())' "$WHEEL_PATH")"

cat > "$TMP_DIR/local-wheel.txt" <<EOF
givp @ ${WHEEL_URL} --hash=sha256:${WHEEL_HASH}
EOF

pip install --no-deps --require-hashes -r "$TMP_DIR/local-wheel.txt"
