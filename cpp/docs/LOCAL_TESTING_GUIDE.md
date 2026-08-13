# Local Package Testing Guide

This page is for package maintenance only. For library usage, installation, and
consumer examples, see `docs/cpp.md`.

## Recommended flow

Run the combined test first:

```powershell
powershell -File scripts/test-both-local.ps1
```

Run the individual scripts only when you need to isolate a failure:

```powershell
powershell -File scripts/test-vcpkg-local.ps1
powershell -File scripts/test-conan-recipe.ps1
```

## Prerequisites

### vcpkg

```powershell
git clone https://github.com/microsoft/vcpkg.git
cd vcpkg
.\bootstrap-vcpkg.bat
$env:PATH = "C:\path\to\vcpkg;$env:PATH"
vcpkg --version
```

### Conan

```powershell
pip install "conan>=2.0"
conan --version
```

## What each script validates

### `scripts/test-both-local.ps1`

- Runs vcpkg overlay validation and Conan recipe validation in sequence
- Produces a single pass/fail summary for registry readiness

### `scripts/test-vcpkg-local.ps1`

- Validates `vcpkg.json`
- Validates `portfile.cmake`
- Installs the port through an overlay
- Optionally builds a `find_package(givp)` consumer

### `scripts/test-conan-recipe.ps1`

- Validates the self-contained ConanCenter template
- Runs `conan create` for the immutable release archive
- Verifies `all/test_package/`

## Manual spot checks

Use these only when a script fails and you need a narrower repro.

### vcpkg overlay

```powershell
mkdir vcpkg_overlay/ports/arnime-givp -Force
Copy-Item cpp/vcpkg_ports/arnime-givp/portfile.cmake vcpkg_overlay/ports/arnime-givp/ -Force
Copy-Item cpp/vcpkg_ports/arnime-givp/vcpkg.json vcpkg_overlay/ports/arnime-givp/ -Force
vcpkg install arnime-givp:x64-windows --overlay-ports=./vcpkg_overlay/ports
```

### Conan recipe

```powershell
cd d:\Projetos Pessoais\GIVP
conan create cpp/conan/conancenter/recipes/givp/all --version 1.0.1 --build=missing -s compiler.cppstd=17 -vv
```

## Common failures

### `SHA512 mismatch`

- Recompute the release tarball hash
- Update `cpp/vcpkg_ports/arnime-givp/portfile.cmake`
- Re-run `scripts/test-vcpkg-local.ps1`

### `Port not found`

- Confirm `--overlay-ports=./vcpkg_overlay/ports`
- Confirm the port files were copied into `vcpkg_overlay/ports/arnime-givp/`

### `conanfile.py not found`

- Use `cpp/conan/conancenter/recipes/givp/all/` as the recipe path.
- Verify `cpp/conan/conancenter/recipes/givp/all/test_package/` still exists.

### `test_package` compilation failure

- Check headers under `cpp/include/givp/`
- Check `cpp/conan/conancenter/recipes/givp/all/test_package/example.cpp`
- Re-run the template `conan create` command above

## After local validation

- For vcpkg submission, use `VCPKG_NOTES.md`
- For Conan Center submission, use `CONAN_NOTES.md`
- For release tagging and artifacts, use `RELEASE_AUTOMATION.md`
