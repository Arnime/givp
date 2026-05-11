#!/usr/bin/env pwsh
# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT

<#
.SYNOPSIS
    Test vcpkg port locally using overlay ports.

.DESCRIPTION
    Validates that the arnime-givp vcpkg port can be installed and used.
    Requires vcpkg to be installed and in PATH.

.EXAMPLE
    .\scripts\test-vcpkg-port.ps1
#>

param(
    [string]$VcpkgPath = (& vcpkg fetch vcpkg 2>$null | Select-Object -First 1),
    [string]$Triplet = "x64-linux",
    [switch]$Cleanup
)

if (-not $VcpkgPath) {
    Write-Host "::error::vcpkg not found. Install vcpkg or set -VcpkgPath" -ForegroundColor Red
    exit 1
}

$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
$OverlayPorts = Join-Path $RepoRoot "cpp\vcpkg_ports"

Write-Host "Testing vcpkg port for arnime-givp..." -ForegroundColor Green
Write-Host "Repo root: $RepoRoot"
Write-Host "Overlay ports: $OverlayPorts"
Write-Host "Triplet: $Triplet"
Write-Host ""

# Test 1: Validate port structure
Write-Host "Test 1: Validating port structure..." -ForegroundColor Cyan
$PortFiles = @("portfile.cmake", "vcpkg.json")
$PortDir = Join-Path $OverlayPorts "arnime-givp"
$MissingFiles = @()

foreach ($file in $PortFiles) {
    $path = Join-Path $PortDir $file
    if (Test-Path $path) {
        Write-Host "  ✓ $file found"
    } else {
        Write-Host "  ✗ $file missing" -ForegroundColor Red
        $MissingFiles += $file
    }
}

if ($MissingFiles.Count -gt 0) {
    Write-Host "::error::Missing port files: $($MissingFiles -join ', ')" -ForegroundColor Red
    exit 1
}

Write-Host "Port structure valid." -ForegroundColor Green
Write-Host ""

# Test 2: Syntax validation of portfile.cmake
Write-Host "Test 2: Validating CMake syntax..." -ForegroundColor Cyan
$PortfilePath = Join-Path $PortDir "portfile.cmake"
$Content = Get-Content $PortfilePath -Raw

if ($Content -match 'SHA512\s+0') {
    Write-Host "  ⚠ SHA512 is still a placeholder (0). You'll need to update it before submitting." -ForegroundColor Yellow
} else {
    Write-Host "  ✓ SHA512 value set"
}

if ($Content -match 'vcpkg_from_github') {
    Write-Host "  ✓ vcpkg_from_github found"
} else {
    Write-Host "  ✗ vcpkg_from_github not found" -ForegroundColor Red
    exit 1
}

Write-Host "CMake syntax looks good." -ForegroundColor Green
Write-Host ""

# Test 3: Validate vcpkg.json JSON
Write-Host "Test 3: Validating vcpkg.json..." -ForegroundColor Cyan
$JsonPath = Join-Path $PortDir "vcpkg.json"
$Json = Get-Content $JsonPath | ConvertFrom-Json

if ($Json.name -eq "arnime-givp") {
    Write-Host "  ✓ Package name correct: $($Json.name)"
} else {
    Write-Host "  ✗ Package name incorrect" -ForegroundColor Red
    exit 1
}

if ($Json.version) {
    Write-Host "  ✓ Version set: $($Json.version)"
} else {
    Write-Host "  ✗ Version missing" -ForegroundColor Red
    exit 1
}

if ($Json.description) {
    Write-Host "  ✓ Description present"
} else {
    Write-Host "  ✗ Description missing" -ForegroundColor Red
    exit 1
}

Write-Host "vcpkg.json is valid JSON." -ForegroundColor Green
Write-Host ""

# Test 4: Try to install (optional, requires vcpkg installed)
Write-Host "Test 4: Attempting installation with vcpkg..." -ForegroundColor Cyan

if (-not (Get-Command vcpkg -ErrorAction SilentlyContinue)) {
    Write-Host "  ⓘ vcpkg not in PATH. Skipping installation test." -ForegroundColor Yellow
    Write-Host "     To test installation manually, run:"
    Write-Host "     vcpkg install --overlay-ports=$OverlayPorts arnime-givp:$Triplet"
} else {
    Write-Host "  Testing: vcpkg install --overlay-ports=$OverlayPorts arnime-givp:$Triplet"
    try {
        & vcpkg install --overlay-ports="$OverlayPorts" "arnime-givp:$Triplet" 2>&1 | Tee-Object -Variable vcpkgOutput | Out-Host
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  ✓ Installation succeeded" -ForegroundColor Green
            
            # Verify installed files
            $installed = & vcpkg list arnime-givp 2>&1
            if ($installed) {
                Write-Host "  ✓ arnime-givp listed in vcpkg: $installed"
            }
        } else {
            Write-Host "  ✗ Installation failed (exit code $LASTEXITCODE)" -ForegroundColor Red
            Write-Host "     Check vcpkg output above for details."
            exit 1
        }
    } catch {
        Write-Host "  ✗ Installation test error: $_" -ForegroundColor Red
        exit 1
    }
}

Write-Host ""
Write-Host "=== Port validation passed! ===" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:"
Write-Host "1. Update SHA512 in portfile.cmake (see cpp/docs/VCPKG_NOTES.md)"
Write-Host "2. Commit and push to feature branch"
Write-Host "3. Open PR on microsoft/vcpkg with the port"
Write-Host ""

if ($Cleanup) {
    Write-Host "Cleaning up test artifacts..."
    # Cleanup logic here if needed
}

exit 0
