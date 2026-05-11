# vcpkg Registry Submission Guide

This page is for maintainer operations only. Run local validation first with
`scripts/test-vcpkg-local.ps1` or `scripts/test-both-local.ps1`.

## Port contents

The staging port lives in `cpp/vcpkg_ports/arnime-givp/`:

- `portfile.cmake`
- `vcpkg.json`

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
vcpkg install arnime-givp:x64-windows --overlay-ports=./cpp/vcpkg_ports
```

## Official submission flow

1. Fork `microsoft/vcpkg`.
2. Create a branch such as `add-givp-header-only`.
3. Copy `cpp/vcpkg_ports/arnime-givp/` into `ports/arnime-givp/`.
4. Verify `ports/arnime-givp/` contains `portfile.cmake` and `vcpkg.json`.
5. Open the PR with the package name, version, license, and repository URL.

If the curated registry review blocks publication due to project maturity, keep
the port distributed through overlay ports or migrate it to a custom registry.
Both paths are valid for end users and keep package installation reproducible.

Suggested PR title:

```text
Add givp: GRASP-ILS-VND with Path Relinking optimizer
```

## Typical review points

- `supports` field too broad or too narrow
- Portfile formatting and helper usage
- Incorrect hash or release URL
- Missing install validation on one platform
- Packaged project maturity requirements for the curated registry

## Fallback publication paths

### Overlay port in this repository

```powershell
git clone https://github.com/Arnime/grasp_ils_vnd_pr.git
vcpkg install arnime-givp --overlay-ports=./grasp_ils_vnd_pr/cpp/vcpkg_ports
```

### Custom git registry

1. Create a dedicated registry repository with `ports/` and `versions/`.
2. Copy `cpp/vcpkg_ports/arnime-givp` into `ports/arnime-givp`.
3. Run `vcpkg x-add-version arnime-givp` in the registry.
4. Point consumers to the registry in `vcpkg-configuration.json`.

## References

- vcpkg docs: <https://learn.microsoft.com/en-us/vcpkg/>
- Header-only example: <https://github.com/microsoft/vcpkg/tree/master/ports/nlohmann-json>
- Contribution guide: <https://github.com/microsoft/vcpkg/blob/master/CONTRIBUTING.md>
