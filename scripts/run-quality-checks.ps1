# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT

<#
.SYNOPSIS
    GIVP Quality Gate checker for Windows (with WSL fallback for C++)

.DESCRIPTION
    Cross-platform wrapper to run quality gates (lint, format-check, typecheck)
    for Python, Julia, Rust, C++, and R. Automatically delegates to WSL or Docker
    for C++ checks if not available locally.

.PARAMETER Language
    Comma-separated languages to check (python, julia, rust, cpp, r).
    Default: "python,rust,julia,cpp,r"

.PARAMETER Mode
    Check mode: "full" (all checks), "lint", "format", "typecheck"
    Default: "full"

.PARAMETER UseWSL
    If true, run C++ via 'wsl make cpp-all' instead of local tools.
    Default: auto-detect

.PARAMETER UseDocker
    If true, run all checks via 'docker-compose' (scripts/local-ci/).
    Default: false

.EXAMPLE
    .\scripts\run-quality-checks.ps1
    # Run all languages, full checks

    .\scripts\run-quality-checks.ps1 -Language python,rust -Mode full
    # Run only Python and Rust

    .\scripts\run-quality-checks.ps1 -Language cpp -UseWSL
    # Run C++ via WSL make

    .\scripts\run-quality-checks.ps1 -UseDocker
    # Run all via docker-compose

#>

param(
    [string]$Language = "python,rust,julia,cpp,r",
    [ValidateSet("full", "lint", "format", "typecheck")]
    [string]$Mode = "full",
    [switch]$UseWSL,
    [switch]$UseDocker,
    [switch]$CleanupBuilds,
    [switch]$Help
)

function Write-Header {
    param([string]$Text)
    Write-Host "`n╔════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "║ $($Text.PadRight(58)) ║" -ForegroundColor Cyan
    Write-Host "╚════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Text)
    Write-Host "✓ $Text" -ForegroundColor Green
}

function Write-Error {
    param([string]$Text)
    Write-Host "✗ $Text" -ForegroundColor Red
}

function Write-Info {
    param([string]$Text)
    Write-Host "ℹ $Text" -ForegroundColor Yellow
}

function Show-Help {
    Write-Host @"
GIVP Quality Gate Checker (Windows)

Usage: .\scripts\run-quality-checks.ps1 [options]

Options:
  -Language     Comma-separated: python, julia, rust, cpp, r (default: all)
  -Mode         Check mode: full (lint+format+typecheck), lint, format, typecheck
  -UseWSL       Force C++ checks via WSL (wsl make cpp-all)
  -UseDocker    Run all via docker-compose (scripts/local-ci/)
    -CleanupBuilds Remove local C++ build artifacts after docker local CI finishes
  -Help         Show this help

Examples:
    .\scripts\run-quality-checks.ps1
    .\scripts\run-quality-checks.ps1 -Language python,rust
    .\scripts\run-quality-checks.ps1 -Language cpp -UseWSL
    .\scripts\run-quality-checks.ps1 -UseDocker
    .\scripts\run-quality-checks.ps1 -UseDocker -CleanupBuilds

Recommended workflow:
    1. .\scripts\run-quality-checks.ps1              # Check what works locally
    2. .\scripts\run-quality-checks.ps1 -UseWSL      # Check C++ via WSL
    3. .\scripts\run-quality-checks.ps1 -UseDocker   # Full CI simulation
"@
}

if ($Help) {
    Show-Help
    exit 0
}

Write-Header "GIVP Quality Gate Checker (Windows)"

$langs = @($Language -split ',' | ForEach-Object { $_.Trim().ToLower() })

# Detect environment capabilities
$hasWSL = $false
$hasDocker = $false
$makePath = ""

try {
    $null = wsl --version 2>$null
    $hasWSL = $true
}
catch { }

try {
    $null = docker --version 2>$null
    $hasDocker = $true
}
catch { }

try {
    $makePath = (Get-Command make -ErrorAction Stop).Source
}
catch { }

Write-Info "Environment: WSL=$hasWSL Docker=$hasDocker Make=$(if ($makePath) { 'yes' } else { 'no' })"

# Route based on user selection
if ($UseDocker -and $hasDocker) {
    Write-Info "Routing via docker-compose (scripts/local-ci/)..."
    $dockerArgs = @("python", "rust", "julia", "cpp", "r")
    if ($CleanupBuilds) {
        $dockerArgs += "--cleanup-builds"
    }
    & bash scripts/local-ci/run.sh @dockerArgs
    if ($LASTEXITCODE -eq 0) {
        Write-Header "Docker Local CI Passed"
    }
    else {
        Write-Error "Docker Local CI failed with exit code $LASTEXITCODE"
        exit 1
    }
    exit 0
}

$results = @{
    passed = @()
    failed = @()
    skipped = @()
}

# Check each language
foreach ($lang in $langs) {
    switch ($lang) {
        "python" {
            Write-Header "Python Quality Checks"
            if ($makePath -or $hasWSL) {
                try {
                    if ($hasWSL) {
                        Write-Info "Routing Python via WSL..."
                        & wsl make python-all
                    }
                    else {
                        & make python-all
                    }
                    if ($LASTEXITCODE -eq 0) {
                        Write-Success "Python checks passed"
                        $results.passed += "python"
                    }
                    else {
                        Write-Error "Python checks failed"
                        $results.failed += "python"
                    }
                }
                catch {
                    Write-Error "Python checks failed: $_"
                    $results.failed += "python"
                }
            }
            else {
                Write-Info "Skipping Python (make not found and WSL not available)"
                $results.skipped += "python"
            }
        }

        "rust" {
            Write-Header "Rust Quality Checks"
            try {
                if ($hasWSL -and -not (Get-Command cargo -ErrorAction SilentlyContinue)) {
                    Write-Info "Routing Rust via WSL..."
                    & wsl make rust-all
                }
                elseif (Get-Command cargo -ErrorAction SilentlyContinue) {
                    & make rust-all
                }
                else {
                    Write-Info "Skipping Rust (cargo not found, WSL not available)"
                    $results.skipped += "rust"
                    continue
                }
                if ($LASTEXITCODE -eq 0) {
                    Write-Success "Rust checks passed"
                    $results.passed += "rust"
                }
                else {
                    Write-Error "Rust checks failed"
                    $results.failed += "rust"
                }
            }
            catch {
                Write-Error "Rust checks failed: $_"
                $results.failed += "rust"
            }
        }

        "julia" {
            Write-Header "Julia Quality Checks"
            try {
                if ($hasWSL -and -not (Get-Command julia -ErrorAction SilentlyContinue)) {
                    Write-Info "Routing Julia via WSL..."
                    & wsl make julia-all
                }
                elseif (Get-Command julia -ErrorAction SilentlyContinue) {
                    & make julia-all
                }
                else {
                    Write-Info "Skipping Julia (julia not found, WSL not available)"
                    $results.skipped += "julia"
                    continue
                }
                if ($LASTEXITCODE -eq 0) {
                    Write-Success "Julia checks passed"
                    $results.passed += "julia"
                }
                else {
                    Write-Error "Julia checks failed"
                    $results.failed += "julia"
                }
            }
            catch {
                Write-Error "Julia checks failed: $_"
                $results.failed += "julia"
            }
        }

        "cpp" {
            Write-Header "C++ Quality Checks"
            if ($UseWSL -or -not (Get-Command clang-format -ErrorAction SilentlyContinue)) {
                if ($hasWSL) {
                    Write-Info "Routing C++ via WSL..."
                    & wsl make cpp-all
                    if ($LASTEXITCODE -eq 0) {
                        Write-Success "C++ checks passed (via WSL)"
                        $results.passed += "cpp"
                    }
                    else {
                        Write-Error "C++ checks failed (via WSL)"
                        $results.failed += "cpp"
                    }
                }
                else {
                    Write-Info "Skipping C++ (clang-format not found and WSL not available)"
                    Write-Info "  ℹ To run C++ checks, install WSL or use: .\scripts\run-quality-checks.ps1 -UseDocker"
                    $results.skipped += "cpp"
                }
            }
            else {
                try {
                    & make cpp-all
                    if ($LASTEXITCODE -eq 0) {
                        Write-Success "C++ checks passed"
                        $results.passed += "cpp"
                    }
                    else {
                        Write-Error "C++ checks failed"
                        $results.failed += "cpp"
                    }
                }
                catch {
                    Write-Error "C++ checks failed: $_"
                    $results.failed += "cpp"
                }
            }
        }

        "r" {
            Write-Header "R Quality Checks"
            try {
                if ($hasWSL -and -not (Get-Command Rscript -ErrorAction SilentlyContinue)) {
                    Write-Info "Routing R via WSL..."
                    & wsl make r-all
                }
                elseif (Get-Command Rscript -ErrorAction SilentlyContinue) {
                    & make r-all
                }
                else {
                    Write-Info "Skipping R (Rscript not found, WSL not available)"
                    $results.skipped += "r"
                    continue
                }
                if ($LASTEXITCODE -eq 0) {
                    Write-Success "R checks passed"
                    $results.passed += "r"
                }
                else {
                    Write-Error "R checks failed"
                    $results.failed += "r"
                }
            }
            catch {
                Write-Error "R checks failed: $_"
                $results.failed += "r"
            }
        }

        default {
            Write-Error "Unknown language: $lang"
        }
    }
}

# Summary
Write-Header "Summary"
if ($results.passed.Count -gt 0) {
    Write-Success "Passed ($($results.passed.Count)): $($results.passed -join ', ')"
}
if ($results.failed.Count -gt 0) {
    Write-Error "Failed ($($results.failed.Count)): $($results.failed -join ', ')"
}
if ($results.skipped.Count -gt 0) {
    Write-Info "Skipped ($($results.skipped.Count)): $($results.skipped -join ', ')"
}

if ($results.failed.Count -gt 0) {
    Write-Error "Some checks failed. Exit code: 1"
    exit 1
}
else {
    Write-Success "All checks passed!"
    exit 0
}
