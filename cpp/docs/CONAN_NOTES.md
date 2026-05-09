# Conan Center Submission Guide

This page is for maintainer operations only. Run local validation first with
`scripts/test-conan-local.ps1` or `scripts/test-both-local.ps1`.

## Recipe contents

The Conan recipe lives in `cpp/conan/`:

- `conanfile.py`
- `test_package/conanfile.py`
- `test_package/CMakeLists.txt`
- `test_package/example.cpp`

## Pre-submission checklist

- [ ] `conan create . --build=missing` passes
- [ ] `test_package/` builds and executes
- [ ] `package_info()` exports `givp::givp`
- [ ] Metadata is complete in `conanfile.py`
- [ ] Exported sources include the public headers and license

## Local validation

```powershell
powershell -File scripts/test-conan-local.ps1
```

Manual repro:

```powershell
cd d:\Projetos Pessoais\grasp_ils_vnd_pr\cpp\conan
conan create . --build=missing -vv
```

## Official submission flow

1. Fork `conan-io/conan-center-index`.
2. Create a branch such as `add/givp`.
3. Copy `cpp/conan/conanfile.py` and `cpp/conan/test_package/` into `recipes/givp/all/`.
4. Add `LICENSE` if required by the target layout.
5. Open the PR with package metadata and validation notes.

Suggested PR title:

```text
givp/1.0.0: Add GRASP-ILS-VND with Path Relinking optimizer
```

## Typical review points

- Missing metadata or incomplete license information
- `test_package/` not matching the exported CMake target
- Platform-specific fixes for Windows or AppleClang
- Layout mismatches under `recipes/givp/all/`

## References

- Conan 2 docs: <https://docs.conan.io/>
- Conan Center guide: <https://github.com/conan-io/conan-center-index/blob/master/docs/README.md>
- Header-only example: <https://github.com/conan-io/conan-center-index/tree/master/recipes/nlohmann_json>
