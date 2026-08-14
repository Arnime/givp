# Release Workflow Automation

This page is for maintainers. For library installation and consumer usage, see
`docs/cpp.md`.

## Trigger

`.github/workflows/release-cpp.yml` is a reusable/manual C++ build workflow.
The central `.github/workflows/release.yml` calls it for each release tag.

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
- Artifact generation for attachment to the central GitHub release

## Standard release flow

1. Update release notes in `CHANGELOG.md` if needed.
2. Make sure local C++ checks are green.
3. Merge the coordinated version bump into `main`; the tag workflow creates
   `vX.Y.Z`.
4. Watch the central **Release** workflow in GitHub Actions.
5. Confirm the single release page contains the tarball and checksum.
6. Review the vcpkg and ConanCenter PRs created or updated by **Sync C++ Registries**.

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

The synchronization uses `add-givp-X.Y.Z` in the two Arnime forks. It copies
the local templates exactly and derives only SHA512 (vcpkg) and SHA256
(ConanCenter) from the immutable release archive. External registry review,
CI, CLA, and merge remain the maintainers' responsibility.
