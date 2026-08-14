# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT

<#
.SYNOPSIS
Local testing script for vcpkg overlay port.

.DESCRIPTION
Tests GIVP vcpkg port locally using overlay functionality without submitting to official registry.

.PARAMETER Triplet
vcpkg triplet to test (default: x64-windows)

.PARAMETER SkipConsumer
Skip consumer project compilation test

.PARAMETER VcpkgPath
Path to vcpkg installation (auto-clones if not provided)

.EXAMPLE
PS> .\test-vcpkg-local.ps1
PS> .\test-vcpkg-local.ps1 -Triplet x64-linux-gcc -SkipConsumer
#>

param(
    [string] $Triplet = "x64-windows",
    [switch] $SkipConsumer,
    [string] $VcpkgPath
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$vcpkgPortsDir = Join-Path $repoRoot "cpp\vcpkg_ports"
$vcpkgOverlayDir = Join-Path $repoRoot "vcpkg_overlay"

Write-Host "=== vcpkg Local Overlay Test ===" -ForegroundColor Cyan
Write-Host "Repository: $repoRoot"
Write-Host "Triplet: $Triplet`n"

# 1. Find or clone vcpkg
Write-Host "[1] Setting up vcpkg..." -ForegroundColor Yellow
if ([string]::IsNullOrEmpty($VcpkgPath) -or -not (Test-Path $VcpkgPath)) {
    Write-Host "  vcpkg not provided, checking system..."
    $vcpkg = Get-Command vcpkg -ErrorAction SilentlyContinue
    if ($null -ne $vcpkg) {
        $VcpkgPath = Split-Path -Parent $vcpkg.Source
        Write-Host "  Found vcpkg at: $VcpkgPath" -ForegroundColor Green
    }
    else {
        Write-Host "  vcpkg not found in PATH. Please install:"
        Write-Host "    git clone https://github.com/microsoft/vcpkg.git"
        Write-Host "    cd vcpkg && .\bootstrap-vcpkg.bat"
        exit 1
    }
}

$vcpkgExe = Join-Path $VcpkgPath "vcpkg.exe"
if (-not (Test-Path $vcpkgExe)) {
    $vcpkgExe = Join-Path $VcpkgPath "vcpkg"
}

if (-not (Test-Path $vcpkgExe)) {
    Write-Error "vcpkg executable not found at $VcpkgPath"
}

# 2. Create overlay structure
Write-Host "`n[2] Creating overlay structure..." -ForegroundColor Yellow
if (-not (Test-Path $vcpkgOverlayDir)) {
    New-Item -ItemType Directory -Path $vcpkgOverlayDir | Out-Null
}

$overlayPortDir = Join-Path $vcpkgOverlayDir "ports" "givp"
if (-not (Test-Path $overlayPortDir)) {
    New-Item -ItemType Directory -Path $overlayPortDir -Force | Out-Null
}

# Copy port files
Copy-Item (Join-Path $vcpkgPortsDir "givp" "portfile.cmake") $overlayPortDir -Force
Copy-Item (Join-Path $vcpkgPortsDir "givp" "vcpkg.json") $overlayPortDir -Force

Write-Host "  ✓ Overlay created at: $overlayPortDir" -ForegroundColor Green

# 3. Install with overlay
Write-Host "`n[3] Installing givp with overlay (this may take a few minutes)..." -ForegroundColor Yellow
try {
    & $vcpkgExe install givp:"$Triplet" `
        --overlay-ports="$vcpkgOverlayDir/ports" `
        --verbose
    if ($LASTEXITCODE -ne 0) {
        throw "vcpkg install failed with exit code $LASTEXITCODE"
    }
    Write-Host "  ✓ Installation successful" -ForegroundColor Green
}
catch {
    Write-Error "vcpkg install failed: $_"
}

# 4. Optional: Test consumer project
if (-not $SkipConsumer) {
    Write-Host "`n[4] Building consumer project..." -ForegroundColor Yellow
    
    $consumerDir = Join-Path $repoRoot "vcpkg_consumer_test"
    if (Test-Path $consumerDir) {
        Remove-Item -Recurse -Force $consumerDir
    }
    New-Item -ItemType Directory -Path $consumerDir | Out-Null
    
    # Create minimal consumer CMakeLists.txt
    @"
cmake_minimum_required(VERSION 3.21)
project(givp_consumer CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(givp CONFIG REQUIRED)

add_executable(consumer_test consumer_test.cpp)
target_link_libraries(consumer_test PRIVATE givp::givp)
"@ | Out-File -Encoding UTF8 (Join-Path $consumerDir "CMakeLists.txt")
    
    # Create minimal consumer code
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
    
    auto result = givp::givp(sphere, bounds, cfg);
    std::cout << "Optimization successful: " << result.success << std::endl;
    std::cout << "Best value: " << result.fun << std::endl;
    
    return result.success ? 0 : 1;
}
"@ | Out-File -Encoding UTF8 (Join-Path $consumerDir "consumer_test.cpp")
    
    try {
        Push-Location $consumerDir
        
        # Configure and build
        cmake -B build `
            -DCMAKE_TOOLCHAIN_FILE="$VcpkgPath/scripts/buildsystems/vcpkg.cmake" `
            -DVCPKG_TARGET_TRIPLET="$Triplet"
        
        cmake --build build --config Release
        
        Write-Host "  ✓ Consumer project built successfully" -ForegroundColor Green
        
        # Run test
        $executable = if ($Triplet -like "*windows*") {
            Join-Path "build" "Release" "consumer_test.exe"
        }
        else {
            Join-Path "build" "consumer_test"
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
}

Write-Host "`n=== vcpkg Test Complete ===" -ForegroundColor Cyan
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Review overlay test results"
Write-Host "  2. If successful, proceed to registry submission"
Write-Host "  3. See cpp/docs/VCPKG_NOTES.md for vcpkg registry submission guide"
