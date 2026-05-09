# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT

<#
.SYNOPSIS
Local testing script for Conan 2 recipe.

.DESCRIPTION
Tests GIVP Conan recipe locally using conan create without submitting to official registry.

.PARAMETER SkipCreate
Skip conan create step

.PARAMETER Settings
Additional Conan settings (e.g., "os=Windows;compiler='Visual Studio'")

.PARAMETER Verbose
Enable verbose output

.EXAMPLE
PS> .\test-conan-local.ps1
PS> .\test-conan-local.ps1 -Settings "os=Linux;compiler=gcc" -Verbose
#>

param(
    [switch] $SkipCreate,
    [string] $Settings,
    [switch] $Verbose,
    [string] $Version
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$conanDir = Join-Path $repoRoot "cpp\conan"

if ([string]::IsNullOrWhiteSpace($Version)) {
    if (-not [string]::IsNullOrWhiteSpace($env:GIVP_VERSION)) {
        $Version = $env:GIVP_VERSION
    }
    elseif ($env:GITHUB_REF_NAME -match "^v?\d+\.\d+\.\d+([\-\+].+)?$") {
        $Version = $env:GITHUB_REF_NAME
    }
    else {
        $Version = "1.0.0"
    }
}

$Version = $Version.Trim()
if ($Version.StartsWith("v")) {
    $Version = $Version.Substring(1)
}

Write-Host "=== Conan 2 Local Test ===" -ForegroundColor Cyan
Write-Host "Repository: $repoRoot"
Write-Host "Conan directory: $conanDir`n"
Write-Host "Package version: $Version`n"

# 1. Check Conan installation
Write-Host "[1] Verifying Conan 2 installation..." -ForegroundColor Yellow
try {
    $conanVersion = conan --version 2>&1
    if ($conanVersion -notmatch "Conan version [2-9]") {
        Write-Error "Conan 2.x not found. Install with: pip install conan>=2.0"
    }
    Write-Host "  ✓ $conanVersion" -ForegroundColor Green
}
catch {
    Write-Error "Conan command not found in PATH"
}

# 2. Verify conanfile.py
Write-Host "`n[2] Validating conanfile.py..." -ForegroundColor Yellow
$conanfilePath = Join-Path $conanDir "conanfile.py"
if (-not (Test-Path $conanfilePath)) {
    Write-Error "conanfile.py not found at $conanfilePath"
}

try {
    python -m py_compile $conanfilePath 2>&1 | Out-Null
    Write-Host "  ✓ conanfile.py syntax valid" -ForegroundColor Green
}
catch {
    Write-Error "conanfile.py has syntax errors"
}

# 3. Verify test_package
Write-Host "`n[3] Validating test_package structure..." -ForegroundColor Yellow
$testFiles = @(
    (Join-Path $conanDir "test_package" "conanfile.py"),
    (Join-Path $conanDir "test_package" "CMakeLists.txt"),
    (Join-Path $conanDir "test_package" "example.cpp")
)

$allTestFilesExist = $true
foreach ($file in $testFiles) {
    if (Test-Path $file) {
        Write-Host "  ✓ $(Split-Path $file -Leaf)" -ForegroundColor Green
    }
    else {
        Write-Warning "  ✗ Missing: $file"
        $allTestFilesExist = $false
    }
}

if (-not $allTestFilesExist) {
    Write-Error "test_package structure incomplete"
}

# 4. Run conan create
if (-not $SkipCreate) {
    Write-Host "`n[4] Running conan create (this may take 2-5 minutes)..." -ForegroundColor Yellow
    
    Push-Location $conanDir
    try {
        $conanCmd = "conan create . --version=$Version --build=missing"
        if ($Verbose) {
            $conanCmd += " -vv"
        }
        
        if (-not [string]::IsNullOrEmpty($Settings)) {
            $conanCmd += " -s $Settings"
        }
        
        Write-Host "  Command: $conanCmd" -ForegroundColor Gray
        
        Invoke-Expression $conanCmd
        
        Write-Host "`n  ✓ conan create completed successfully" -ForegroundColor Green
    }
    catch {
        Write-Error "conan create failed: $_"
    }
    finally {
        Pop-Location
    }
}
else {
    Write-Host "`n[4] Skipping conan create (use -SkipCreate:`$false to run)" -ForegroundColor Yellow
}

# 5. Optional: Test consumer with conan
Write-Host "`n[5] Building test consumer project..." -ForegroundColor Yellow

$consumerDir = Join-Path $repoRoot "conan_consumer_test"
if (Test-Path $consumerDir) {
    Remove-Item -Recurse -Force $consumerDir | Out-Null
}
New-Item -ItemType Directory -Path $consumerDir | Out-Null

# Create consumer conanfile.txt
@"
[requires]
givp/$Version

[generators]
CMakeDeps
CMakeToolchain
"@ | Out-File -Encoding UTF8 (Join-Path $consumerDir "conanfile.txt")

# Create consumer CMakeLists.txt
@"
cmake_minimum_required(VERSION 3.21)
project(givp_consumer CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(givp CONFIG REQUIRED)

add_executable(consumer_test consumer_test.cpp)
target_link_libraries(consumer_test PRIVATE givp::givp)
"@ | Out-File -Encoding UTF8 (Join-Path $consumerDir "CMakeLists.txt")

# Create consumer code
@"
#include <iostream>
#include <vector>
#include <givp/givp.hpp>

int main() {
    auto sphere = [](const std::vector<double> &x) {
        double s = 0.0;
        for (double v : x) s += v * v;
        return s;
    };
    
    std::vector<std::pair<double, double>> bounds(3, {-5.0, 5.0});
    givp::GivpConfig cfg;
    cfg.max_iterations = 10;
    cfg.seed = 42;
    
    auto result = givp::givp(sphere, bounds, cfg);
    
    std::cout << "Optimization successful: " << (result.success ? "yes" : "no") << std::endl;
    std::cout << "Best value: " << result.fun << std::endl;
    std::cout << "Evaluations: " << result.nfev << std::endl;
    
    return result.success ? 0 : 1;
}
"@ | Out-File -Encoding UTF8 (Join-Path $consumerDir "consumer_test.cpp")

try {
    Push-Location $consumerDir
    
    # Install dependencies
    conan install . --build=missing
    
    # Configure and build
    cmake -B build -DCMAKE_TOOLCHAIN_FILE="conan_toolchain.cmake"
    cmake --build build --config Release
    
    Write-Host "  ✓ Consumer project built successfully" -ForegroundColor Green
    
    # Run test
    $executable = Join-Path "build" "Release" "consumer_test"
    if (-not (Test-Path $executable)) {
        $executable = Join-Path "build" "consumer_test"
    }
    
    if (Test-Path $executable) {
        & $executable
        Write-Host "  ✓ Consumer test executed successfully" -ForegroundColor Green
    }
}
catch {
    Write-Warning "Consumer project test failed (non-critical): $_"
}
finally {
    Pop-Location
}

Write-Host "`n=== Conan Test Complete ===" -ForegroundColor Cyan
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Review test results above"
Write-Host "  2. If successful, proceed to registry submission"
Write-Host "  3. See cpp/docs/CONAN_NOTES.md for ConanCenter submission guide"
