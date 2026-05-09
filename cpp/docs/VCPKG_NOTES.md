# vcpkg Registry Submission Guide

This page is for maintainer operations only. Run local validation first with
`scripts/test-vcpkg-local.ps1` or `scripts/test-both-local.ps1`.

## Port contents

The staging port lives in `cpp/vcpkg_ports/givp/`:

- `portfile.cmake`
- `vcpkg.json`
- `METADATA.json`

## Pre-submission checklist

- [ ] Update the release SHA512 in `portfile.cmake`
- [ ] Validate the overlay locally
- [ ] Confirm headers install under `include/givp/`
- [ ] Confirm `givpConfig.cmake` is installed
- [ ] Confirm `find_package(givp CONFIG REQUIRED)` works in a consumer

## Refresh the release hash

```bash
wget https://github.com/Arnime/grasp_ils_vnd_pr/archive/refs/tags/v1.0.0.tar.gz
sha512sum v1.0.0.tar.gz
```

Replace the placeholder in `vcpkg_from_github(... SHA512 <value>)`.

## Local validation

```powershell
powershell -File scripts/test-vcpkg-local.ps1
```

Manual repro:

```powershell
vcpkg install givp:x64-windows --overlay-ports=./cpp/vcpkg_ports
```

## Official submission flow

1. Fork `microsoft/vcpkg`.
2. Create a branch such as `add-givp-header-only`.
3. Copy `cpp/vcpkg_ports/givp/` into `ports/givp/`.
4. Verify `ports/givp/` contains `portfile.cmake`, `vcpkg.json`, and `METADATA.json`.
5. Open the PR with the package name, version, license, and repository URL.

Suggested PR title:

```text
Add givp: GRASP-ILS-VND with Path Relinking optimizer
```

## Typical review points

- `supports` field too broad or too narrow
- Portfile formatting and helper usage
- Incorrect hash or release URL
- Missing install validation on one platform

## References

- vcpkg docs: <https://learn.microsoft.com/en-us/vcpkg/>
- Header-only example: <https://github.com/microsoft/vcpkg/tree/master/ports/nlohmann-json>
- Contribution guide: <https://github.com/microsoft/vcpkg/blob/master/CONTRIBUTING.md>
