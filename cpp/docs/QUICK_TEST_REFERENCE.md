# Local Package Testing Quick Reference

Use this file when you only need the commands.

## Recommended

```powershell
cd d:\Projetos Pessoais\grasp_ils_vnd_pr
powershell -File scripts/test-both-local.ps1
```

## Quick mode

```powershell
powershell -File scripts/test-both-local.ps1 -QuickMode
```

## vcpkg only

```powershell
powershell -File scripts/test-vcpkg-local.ps1
powershell -File scripts/test-vcpkg-local.ps1 -Triplet x64-windows
powershell -File scripts/test-vcpkg-local.ps1 -SkipConsumer
```

## Conan only

```powershell
pip install "conan>=2.0"
conan --version
powershell -File scripts/test-conan-local.ps1
powershell -File scripts/test-conan-local.ps1 -SkipCreate
powershell -File scripts/test-conan-local.ps1 -Verbose
```

## Manual repros

### vcpkg overlay

```powershell
mkdir vcpkg_overlay/ports/arnime-givp -Force
Copy-Item cpp/vcpkg_ports/arnime-givp/portfile.cmake vcpkg_overlay/ports/arnime-givp/ -Force
Copy-Item cpp/vcpkg_ports/arnime-givp/vcpkg.json vcpkg_overlay/ports/arnime-givp/ -Force
vcpkg install arnime-givp:x64-windows --overlay-ports=./vcpkg_overlay/ports
```

### Conan recipe

```powershell
cd d:\Projetos Pessoais\grasp_ils_vnd_pr\cpp\conan
conan create . --build=missing -vv
```

## Next docs

- Detailed flow: `LOCAL_TESTING_GUIDE.md`
- vcpkg submission: `VCPKG_NOTES.md`
- Conan submission: `CONAN_NOTES.md`
- Release tagging: `RELEASE_AUTOMATION.md`
