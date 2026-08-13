# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT

<#
.SYNOPSIS
Run both vcpkg and Conan local tests.

.DESCRIPTION
Executes vcpkg overlay test and Conan recipe test sequentially with consolidated reporting.

.PARAMETER SkipVcpkg
Skip vcpkg overlay test

.PARAMETER SkipConan
Skip Conan create test

.PARAMETER QuickMode
Disable consumer project tests (faster)

.EXAMPLE
PS> .\test-both-local.ps1
PS> .\test-both-local.ps1 -QuickMode -SkipConan
#>

param(
    [switch] $SkipVcpkg,
    [switch] $SkipConan,
    [switch] $QuickMode
)

$ErrorActionPreference = "Continue"
$repoRoot = Split-Path -Parent $PSScriptRoot
$scriptsDir = $PSScriptRoot

Write-Host "╔════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║         GIVP Local Package Manager Test Suite              ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan

$results = @{
    vcpkg = "skipped"
    conan = "skipped"
}

# Run vcpkg test
if (-not $SkipVcpkg) {
    Write-Host "`n╔═══════════════════════════════════════════════════════════╗" -ForegroundColor Yellow
    Write-Host "║  TEST 1: vcpkg Overlay (Local Registry)                   ║" -ForegroundColor Yellow
    Write-Host "╚═══════════════════════════════════════════════════════════╝" -ForegroundColor Yellow
    
    try {
        $vcpkgArgs = @()
        if ($QuickMode) { $vcpkgArgs += "-SkipConsumer" }
        
        & (Join-Path $scriptsDir "test-vcpkg-local.ps1") @vcpkgArgs
        $results.vcpkg = "PASSED ✓"
        Write-Host "`n✓ vcpkg test passed" -ForegroundColor Green
    }
    catch {
        $results.vcpkg = "FAILED ✗"
        Write-Host "`n✗ vcpkg test failed: $_" -ForegroundColor Red
    }
}

# Run Conan test
if (-not $SkipConan) {
    Write-Host "`n╔═══════════════════════════════════════════════════════════╗" -ForegroundColor Yellow
    Write-Host "║  TEST 2: ConanCenter Recipe Template                     ║" -ForegroundColor Yellow
    Write-Host "╚═══════════════════════════════════════════════════════════╝" -ForegroundColor Yellow
    
    try {
        $conanArgs = @()
        if ($QuickMode) { $conanArgs += "-SkipCreate" }
        
        & (Join-Path $scriptsDir "test-conan-recipe.ps1") `
            -RecipePath "cpp\conan\conancenter\recipes\givp\all" `
            -Version "1.0.1" `
            @conanArgs
        $results.conan = "PASSED ✓"
        Write-Host "`n✓ Conan test passed" -ForegroundColor Green
    }
    catch {
        $results.conan = "FAILED ✗"
        Write-Host "`n✗ Conan test failed: $_" -ForegroundColor Red
    }
}

# Summary Report
Write-Host "`n╔════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║                    TEST SUMMARY                            ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan

Write-Host ""
Write-Host "Package Manager    | Status" -ForegroundColor White
Write-Host "─────────────────────────────────────────────────────────────"

foreach ($pm in @("vcpkg", "conan")) {
    $status = $results[$pm]
    $color = if ($status -like "*PASSED*") { "Green" } elseif ($status -like "*FAILED*") { "Red" } else { "Yellow" }
    Write-Host "$pm".PadRight(19) + "| $status" -ForegroundColor $color
}

Write-Host ""
Write-Host "═════════════════════════════════════════════════════════════" -ForegroundColor Cyan

$allPassed = ($results.Values | Where-Object { $_ -like "*PASSED*" }).Count -eq ($results.Values | Where-Object { $_ -ne "skipped" }).Count

if ($allPassed) {
    Write-Host "✓ ALL TESTS PASSED - Ready for registry submission!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Yellow
    Write-Host "  1. Review cpp/docs/VCPKG_NOTES.md for vcpkg submission"
    Write-Host "  2. Review cpp/docs/CONAN_NOTES.md for Conan submission"
    Write-Host "  3. Create pull requests to respective registries"
    exit 0
}
else {
    Write-Host "✗ SOME TESTS FAILED - Review errors above" -ForegroundColor Red
    exit 1
}
