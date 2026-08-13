# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT

<#
.SYNOPSIS
Local validation script for Conan 2 recipe.

.DESCRIPTION
Validates Conan 2 recipe structure and attempts local conan create.
Requires: Conan 2.x installed and available in PATH.

.EXAMPLE
PS> .\test-conan-recipe.ps1
#>

param(
    [switch] $SkipCreate,
    [string] $ConanVersion = "2.0",
    [string] $RecipePath = "cpp\conan\conancenter\recipes\givp\all",
    [string] $Version = "1.0.1"
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$conanDir = Join-Path $repoRoot $RecipePath
$testPackageDir = Join-Path $conanDir "test_package"

Write-Host "=== Conan 2 Recipe Validation ===" -ForegroundColor Cyan

# 1. Check Conan installation
Write-Host "`n[1] Checking Conan 2 installation..."
try {
    $conanVersion = conan --version 2>&1
    if ($conanVersion -notmatch "Conan version [2-9]") {
        Write-Error "Conan 2.x not found. Please install: pip install conan>=2.0"
    }
    Write-Host "✓ $conanVersion" -ForegroundColor Green
}
catch {
    Write-Error "Conan command not found in PATH. Please install Conan 2.x"
}

# 2. Validate conanfile.py syntax
Write-Host "`n[2] Validating conanfile.py..."
$conanfilePath = Join-Path $conanDir "conanfile.py"
if (-not (Test-Path $conanfilePath)) {
    Write-Error "conanfile.py not found at $conanfilePath"
}

try {
    # Python syntax check
    python -m py_compile $conanfilePath
    Write-Host "✓ conanfile.py syntax valid" -ForegroundColor Green
}
catch {
    Write-Error "conanfile.py has syntax errors"
}

# 3. Validate test_package structure
Write-Host "`n[3] Validating test_package structure..."
$files = @(
    (Join-Path $testPackageDir "conanfile.py"),
    (Join-Path $testPackageDir "CMakeLists.txt"),
    (Join-Path $testPackageDir "example.cpp")
)

foreach ($file in $files) {
    if (Test-Path $file) {
        Write-Host "✓ $(Split-Path $file -Leaf)" -ForegroundColor Green
    }
    else {
        Write-Error "Missing: $file"
    }
}

# 4. Optional: Run conan create
if (-not $SkipCreate) {
    Write-Host "`n[4] Testing conan create (this may take a few minutes)..."
    Push-Location $conanDir
    try {
        $createArguments = @("create", ".", "--build=missing")
        if (-not [string]::IsNullOrWhiteSpace($Version)) {
            $createArguments += "--version=$Version"
        }
        Write-Host "  Running: conan $($createArguments -join ' ')"
        conan @createArguments
        Write-Host "✓ conan create succeeded" -ForegroundColor Green
    }
    catch {
        Write-Warning "conan create failed. Check output above for details."
        Write-Host "  (Pass -SkipCreate to skip this step)"
    }
    finally {
        Pop-Location
    }
}
else {
    Write-Host "`n[4] Skipping conan create (use -SkipCreate:$false to run)" -ForegroundColor Yellow
}

Write-Host "`n=== Validation Complete ===" -ForegroundColor Cyan
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Review cpp/docs/CONAN_NOTES.md for submission guide"
Write-Host "  2. Fork conan-center-index repository"
Write-Host "  3. Copy cpp/conan/conancenter/recipes/givp/ to recipes/givp/"
Write-Host "  4. Create PR with description"
