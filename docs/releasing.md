# Release process

GIVP uses one release version across its Python, Rust, Julia, R, and C++
packages. A push to `main` that changes a version manifest creates the matching
`vX.Y.Z` tag and triggers the central release workflow.

## Prepare a release

1. Update the version to the same `X.Y.Z` value in `pyproject.toml`,
   `rust/Cargo.toml`, `julia/Project.toml`, `r/DESCRIPTION`, and
   `cpp/CMakeLists.txt`.
2. Update release notes as appropriate and merge the change into `main`.
3. The **Auto Tag on Version Bump** workflow validates that all five manifests
   agree and creates `vX.Y.Z` when that tag does not already exist.
4. Follow the **Release** workflow for that tag. It publishes Python to PyPI,
   Rust to crates.io, attaches R and C++ artifacts to the GitHub release, and
   opens the Julia registration request.

## crates.io credentials and retries

Store the crates.io API token as `CARGO_REGISTRY_TOKEN` in the protected GitHub
environment named `crates-io`. Do not add the token to workflow files,
repository secrets, source code, or local configuration committed to Git.

The central workflow validates the Rust package, verifies the tag matches
`rust/Cargo.toml`, and checks crates.io before publishing. If a prior run has
already published the version, a rerun reports success without attempting to
overwrite the immutable crate version. Otherwise it requires the environment
secret, publishes, and waits until the version is visible in the registry.

`Dry-run crates.io` remains the non-publishing Rust gate for pull requests and
Rust changes on `main`. It validates all five manifests and reports the tag it
expects (`vX.Y.Z`) on every run. A pull request does not receive an actual Git
tag; the tag is created only after its merge to `main`, where the central
release workflow compares that real tag to the Rust manifest.

## Registry boundaries

The tag-triggered C++ workflow builds, tests, and attaches release artifacts.
Its vcpkg port and Conan recipe remain staging material: official vcpkg and
ConanCenter publication requires a pull request to their respective upstream
repositories. Julia registration is also asynchronous after the workflow opens
the Registrator request.
