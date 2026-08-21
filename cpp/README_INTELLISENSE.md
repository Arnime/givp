# C++ IntelliSense & Build Setup

This document explains how to fix IntelliSense issues and understand the C++
build setup for this project.

---

## Quick Fix: IntelliSense Not Working?

If you see red squiggles or unresolved includes in your C++ files, run:

**Windows (PowerShell):**

```powershell
.\scripts\setup-intellisense.ps1
```

**Linux/macOS (Bash):**

```bash
bash scripts/setup-intellisense.sh
```

This generates `cpp/build/default/compile_commands.json`, which clangd uses for
accurate IntelliSense.

---

## Build Directory Structure

All C++ builds go into `cpp/build/`:

```text
cpp/
  ├─ build/
  │  ├─ default/          ← Main build + tests (IntelliSense here)
  │  ├─ tidy/             ← clang-tidy analysis
  │  ├─ package/          ← CMake package installation
  │  ├─ install/          ← Installed headers + cmake config
  │  ├─ consumer/         ← find_package consumer test
  │  ├─ coverage/         ← Coverage build (debug)
  │  ├─ benchmarks/       ← Benchmark build
  │  ├─ sonar/            ← Sonar compile database
  │  └─ local-ci*/        ← Local CI builds
  ├─ include/             (public headers)
  ├─ tests/               (test sources)
  ├─ benchmarks/          (benchmark sources)
  ├─ conan/conancenter/   (ConanCenter recipe template)
  ├─ vcpkg_ports/         (vcpkg port staging)
  ├─ consumer_check/      (find_package validation)
  └─ docs/                (operational guides)
```

---

## VS Code Configuration

The `.vscode/settings.json` file configures:

- **CMake source directory:** `cpp/`
- **CMake build directory:** `cpp/build/default/` (default for IntelliSense)
- **C++ standard:** C++17
- **IntelliSense engine:** clangd (via `.clangd` config) + Tag Parser

### To manually trigger CMake configuration in VS Code

1. **Command Palette:** `Ctrl+Shift+P` (Cmd+Shift+P on macOS)
2. **Type:** "CMake: Configure"
3. **Select:** Visual Studio 2022 (or your compiler)

Or use the bottom status bar CMake widget.

---

## Common Issues

### Issue: "Cannot find givp/givp.hpp"

**Cause:** IntelliSense database not generated yet.

**Fix:**

```bash
# Generate compile_commands.json
bash scripts/setup-intellisense.sh   # Linux/macOS
# or
.\scripts\setup-intellisense.ps1    # Windows (PowerShell)

# Optional: Also build to validate
cmake --build cpp/build/default
```

### Issue: Slow IntelliSense

**Possible causes:**

- Build directory has too many dependencies cached
- clangd index not updated

**Fix:**

```bash
# Reconfigure with --force
bash scripts/setup-intellisense.sh --force   # Linux/macOS
# or
.\scripts\setup-intellisense.ps1 -Force     # Windows (PowerShell)
```

### Issue: "Command 'cl.exe not found" (Windows MSVC)

**Cause:** MSVC compiler not in PATH.

**Fix:**

1. Run VS Code from Developer Command Prompt for VS 2022

   ```bash
   "C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\Tools\VsDevCmd.bat"
   && code
   ```

2. Or configure CMake generator explicitly in `.vscode/settings.json`:

   ```json
   "cmake.configureArgs": [
       "-G", "Ninja Multi-Config",
       "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON"
   ]
   ```

---

## Building from Command Line

### Quick test build

```bash
cmake -S cpp -B cpp/build/default -DGIVP_BUILD_TESTS=ON
cmake --build cpp/build/default
ctest --test-dir cpp/build/default --output-on-failure
```

### Package installation

```bash
cmake -S cpp -B cpp/build/package-install \
  -DCMAKE_INSTALL_PREFIX=./cpp/build/package-install/install \
  -DGIVP_BUILD_TESTS=OFF \
  -DGIVP_BUILD_BENCHMARKS=OFF
cmake --build cpp/build/package-install
cmake --install cpp/build/package-install
```

### Benchmarks

```bash
cmake -S cpp -B cpp/build/benchmarks -DGIVP_BUILD_BENCHMARKS=ON
cmake --build cpp/build/benchmarks
./cpp/build/benchmarks/benchmarks/givp_benchmarks
```

### Coverage

```bash
cmake -S cpp -B cpp/build/coverage \
  -DCMAKE_BUILD_TYPE=Debug \
  -DCMAKE_CXX_FLAGS="--coverage" \
  -DGIVP_BUILD_TESTS=ON
cmake --build cpp/build/coverage
ctest --test-dir cpp/build/coverage --output-on-failure
```

---

## Files of Interest

- [CMakeLists.txt](CMakeLists.txt) — Main C++ build configuration
- [.clang-format](.clang-format) — Code formatting rules
- [.clang-tidy](.clang-tidy) — Static analysis rules
- [.clangd](.clangd) — clangd IntelliSense configuration
- [.vscode/settings.json](../.vscode/settings.json) — VS Code CMake config (root)
- [cpp/conan/conancenter/recipes/givp/all/conanfile.py](conan/conancenter/recipes/givp/all/conanfile.py) — ConanCenter recipe template
- [cpp/vcpkg_ports/arnime-givp/](vcpkg_ports/arnime-givp/) — vcpkg port
- [docs/RELEASE_AUTOMATION.md](docs/RELEASE_AUTOMATION.md) —
  Release workflow

---

## References

- CMake: <https://cmake.org>
- clangd: <https://clangd.llvm.org>
- clang-tidy: <https://clang.llvm.org/extra/clang-tidy/>
- CMake Tools (VS Code): <https://vector-of-bool.github.io/docs/vscode-cmake-tools/>

---

**Last Updated:** May 8, 2026  
**Status:** ✅ Production Ready
