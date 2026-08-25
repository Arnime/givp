# Release process

GIVP uses one release version across its Python, Rust, Julia, R, and C++
packages. A push to `main` that changes a version manifest creates the matching
`vX.Y.Z` tag and triggers the central release workflow.

## Workflow architecture

`Release` is the only workflow that operators start manually. It validates the
existing tag before any checkout and then calls focused reusable workflows:

```text
release-context
      |
      +-- release-python --+
      +-- release-cpp -----+-- release-provenance
      +-- release-r -------+          |
                                      +-- publish-python
                                      +-- publish-rust
                                      +-- register-julia
                                      +-- sync-cpp-registries

release-r -- verify-r-universe (non-blocking)
```

The Python, C++, and R builds run in parallel. Each returns an artifact name and
base64-encoded hashes to the provenance workflow. That workflow combines the
subjects, generates SLSA provenance, verifies the release asset, and attaches
all language artifacts. External publication starts only after this barrier
succeeds. PyPI publishing remains an inline job in `release.yml` because
[PyPI Trusted Publishing does not support reusable workflows][pypi-reusable].
The other specialized release workflows expose `workflow_call` contracts and
are not manual entry points.

## Prepare a release

1. Update the version to the same `X.Y.Z` value in `python/pyproject.toml`,
   `rust/Cargo.toml`, `julia/Project.toml`, `r/DESCRIPTION`, and
   `cpp/CMakeLists.txt`, `cpp/vcpkg_ports/givp/vcpkg.json`, and the
   ConanCenter template under `cpp/conan/conancenter/recipes/givp/`.
2. Update release notes as appropriate and merge the change into `main`.
3. The **Auto Tag on Version Bump** workflow validates that all five manifests
   agree and creates `vX.Y.Z` when that tag does not already exist.
4. Follow the single **Release** workflow for that tag. It publishes Python to
   PyPI and Rust to crates.io, attaches R and C++ artifacts to the one GitHub
   Release, opens the Julia registration request, and updates the external C++
   registry pull requests.

Do not use GitHub's **Create a new release** interface for normal releases.
For a manual rerun, use **Actions → Release → Run workflow** and provide the
existing `vX.Y.Z` tag. Do not invoke specialized workflows directly. The
workflow builds all official artifacts, generates SLSA provenance before
attaching release assets, and only then publishes to external registries. If a
release is created directly in the GitHub interface, the provenance fallback
checks it and rebuilds only when its `.intoto.jsonl` asset is missing.

## crates.io credentials and retries

Store the crates.io API token as `CARGO_REGISTRY_TOKEN` in the protected GitHub
environment named `crates-io`. Do not add the token to workflow files, source
code, or local configuration committed to Git.
The environment secret must use that exact name; an empty value intentionally
fails the release instead of silently skipping publication.

Configure it under **Settings → Environments → crates-io → Environment
secrets**. For compatibility with an existing repository- or organization-level
secret, `release.yml` explicitly forwards only `CARGO_REGISTRY_TOKEN`. A secret
defined in the protected `crates-io` environment takes precedence in the
reusable workflow.

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

## C++ registry synchronization

`cpp/vcpkg_ports/givp/` and `cpp/conan/conancenter/recipes/givp/` are the
versioned sources of truth. The central release calls **Sync C++ Registries**
after C++ artifacts are attached. It updates the branches
`add-givp-X.Y.Z` in `Arnime/vcpkg` and `Arnime/conan-center-index`, derives
only the archive hashes in those forks, and creates or updates the upstream
PRs. A template change on `main` updates an already-open PR only; without a
matching release tag or PR it succeeds without writing to either fork.

Create `REGISTRY_FORK_TOKEN` as a fine-grained PAT with **Contents: read and
write** plus **Pull requests: read and write**, restricted to the two Arnime
forks. Store it in the protected `registry-forks` environment. The forks remain
ignored local clones, not submodules. vcpkg and ConanCenter still require their
own CI, CLA where applicable, review, and maintainer merge; this automation
never merges external PRs.

For compatibility with an existing repository- or organization-level secret,
`release.yml` explicitly forwards only `REGISTRY_FORK_TOKEN`. A secret defined
in the protected `registry-forks` environment takes precedence.

[pypi-reusable]: https://docs.pypi.org/trusted-publishers/troubleshooting/#reusable-workflows-on-github
