# Conan Center Submission Guide

This page is for maintainer operations only. Run local validation first with
`scripts/test-conan-recipe.ps1` or `scripts/test-both-local.ps1`.

## Recipe contents

The self-contained recipe submitted to ConanCenter is kept in
`cpp/conan/conancenter/recipes/givp/`:

- `config.yml`
- `all/conanfile.py`
- `all/conandata.yml`
- `all/test_package/`

## Pre-submission checklist

- [ ] `conan create cpp/conan/conancenter/recipes/givp/all --version 1.0.1 --build=missing` passes
- [ ] `test_package/` builds and executes
- [ ] `package_info()` exports `givp::givp`
- [ ] Metadata is complete in `conanfile.py`
- [ ] Exported sources include the public headers and license

## Local validation

```powershell
powershell -File scripts/test-conan-recipe.ps1
```

Manual repro:

```powershell
conan create cpp/conan/conancenter/recipes/givp/all --version 1.0.1 --build=missing -s compiler.cppstd=17 -vv
```

## Official submission flow

1. Fork `conan-io/conan-center-index`.
2. Update the fork from `conan-io/conan-center-index:master` and create a branch such as `add-givp-1.0.1`.
3. Copy `cpp/conan/conancenter/recipes/givp/` into `recipes/givp/`.
4. Open the PR with package metadata, source URL, SHA256 validation, and local validation notes.

Suggested PR title:

```text
givp/1.0.1: Add GRASP-ILS-VND with Path Relinking optimizer
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
