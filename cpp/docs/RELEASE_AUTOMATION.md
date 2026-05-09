# Release Workflow Automation

This page is for maintainers. For library installation and consumer usage, see
`docs/cpp.md`.

## Trigger

The release workflow runs from `.github/workflows/release-cpp.yml` on:

- Push of a tag matching `v*`
- Manual `workflow_dispatch` with a tag input

Accepted tags follow semantic versioning, for example:

- `v1.0.0`
- `v1.1.0-rc1`
- `v2.0.0+build.1`

## What the workflow validates

- Semantic version extraction from the tag
- Multi-platform test matrix on GCC, Clang, MSVC, and AppleClang
- CMake install layout under `install/`
- Consumer validation through `find_package(givp)`
- Source tarball generation and SHA256 checksum
- GitHub release creation with attached assets

## Standard release flow

1. Update release notes in `CHANGELOG.md` if needed.
2. Make sure local C++ checks are green.
3. Create an annotated tag.
4. Push the tag.
5. Watch the workflow in GitHub Actions.
6. Confirm the release page contains the tarball and checksum.
7. If registry publication is needed, continue with `VCPKG_NOTES.md` and `CONAN_NOTES.md`.

Example:

```bash
git tag -a v1.0.0 -m "Release v1.0.0"
git push origin v1.0.0
```

## Artifacts

The workflow publishes:

- `givp-cpp-<version>.tar.gz`
- `givp-cpp-<version>.tar.gz.sha256`

The tarball includes the C++ source tree plus the root license and changelog.

## Common failures

### Invalid semantic version

- Confirm the tag starts with `v`
- Confirm the tag uses full semver

### Platform-specific test failure

- Reproduce locally with the matching compiler when possible
- Inspect the failing job in Actions before retagging

### Package install validation failure

- Confirm `givpConfig.cmake` is installed
- Confirm the consumer under `cpp/consumer_check/` still builds

## After a successful release

- Use `VCPKG_NOTES.md` for the vcpkg registry PR
- Use `CONAN_NOTES.md` for the Conan Center PR
- Use `cpp/README_INTELLISENSE.md` if the issue is local CMake or IntelliSense setup
