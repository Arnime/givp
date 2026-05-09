#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT

set -euo pipefail

cat <<'EOF'
┌─ C++ IntelliSense Setup ──────────────────────────────────────────────────┐
│                                                                            │
│ This script initializes clangd IntelliSense by generating a compilation   │
│ database (compile_commands.json) that provides accurate C++ IntelliSense. │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
EOF

BUILD_DIR="cpp/build/default"
FORCE=false

if [ "${1:-}" = "--force" ]; then
  FORCE=true
fi

if [ -d "$BUILD_DIR" ] && [ "$FORCE" = false ]; then
  cat <<EOF

⚠️  Build directory already exists at: $BUILD_DIR

Options:
  1. The build is already initialized (compile_commands.json exists)
  2. Run with --force to reconfigure: $0 --force

EOF
  exit 0
fi

if [ "$FORCE" = true ] && [ -d "$BUILD_DIR" ]; then
  echo "🗑️  Removing existing build directory..."
  rm -rf "$BUILD_DIR"
fi

echo ""
echo "🔧 Configuring CMake for C++ IntelliSense..."
echo ""

cmake -S cpp -B "$BUILD_DIR" \
  -DCMAKE_BUILD_TYPE=Release \
  -DGIVP_BUILD_TESTS=ON \
  -DGIVP_BUILD_BENCHMARKS=OFF \
  -DCMAKE_EXPORT_COMPILE_COMMANDS=ON

echo ""
echo "✅ IntelliSense initialized!"
echo ""
echo "   Compilation database: $BUILD_DIR/compile_commands.json"
echo "   clangd will now provide accurate C++ IntelliSense"
echo ""
echo "📌 Optional: Build the project for additional validation:"
echo "   cmake --build $BUILD_DIR"
echo ""
