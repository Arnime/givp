# Conan 2 Recipe for GIVP

This directory contains the Conan 2 recipe for publishing GIVP to ConanCenter.

## Directory Structure

```text
cpp/conan/
├── conanfile.py              # Main Conan recipe (Conan 2.x format)
├── test_package/
│   ├── conanfile.py          # Test consumer conanfile
│   ├── CMakeLists.txt        # CMake configuration for test
│   └── example.cpp           # Example usage of GIVP
└── README.md                 # This file
```

## Quick Start

### Local Testing

```bash
# Ensure Conan 2.x is installed
conan --version  # Should show version 2.x.x

# Test the recipe locally
cd cpp/conan
conan create . --build=missing

# This will:
# 1. Download sources (or use local cpp/ directory)
# 2. Build package (no-op for header-only)
# 3. Run test_package (compile + execute example)
```

### Submission to ConanCenter

See [cpp/docs/CONAN_NOTES.md](../docs/CONAN_NOTES.md) for detailed
    submission instructions.

**TL;DR:**

1. Fork <https://github.com/conan-io/conan-center-index>
2. Copy `cpp/conan/` contents to `recipes/givp/all/`
3. Open PR with title: `givp/1.0.0: Add GRASP-ILS-VND with Path Relinking optimizer`
4. Address review feedback from maintainers
5. Merge and package is published

## Key Points

- **Header-only**: No compilation required, just copy headers
- **C++17**: Requires C++17 compiler
- **Zero dependencies**: No runtime or build dependencies
- **CMake integration**: Provides `givp::givp` target via `find_package()`

## Testing Commands

```bash
# Windows PowerShell
powershell -File ../../scripts/test-conan-recipe.ps1

# Or directly
conan create . --build=missing -s os=Windows -s compiler="Visual Studio" -s compiler.version=16
```

## Troubleshooting

- **"Conan command not found"**: Install with `pip install conan>=2.0`
- **Test compilation fails**: Ensure C++17 compiler is available
- **SHA512 mismatch**: conanfile.py will auto-fetch from GitHub releases

See cpp/docs/CONAN_NOTES.md for detailed troubleshooting.
